"""Consulta pequeña y real a SICOP que registra fecha, procedencia y validaciones (NLC-01).

No usa MongoDB. Guarda solo identificadores públicos, conteos y clasificaciones: ni textos,
ni archivos, ni las URLs firmadas de los anexos. Uso:

    uv run python scripts/sicop_probe.py --output artifacts/sicop-probe.json
"""

import argparse
import collections
import hashlib
import json
import re
import tempfile
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import httpx
from pypdf import PdfReader

from nexolicitcr.documents import DocumentError, download, metadata_get
from nexolicitcr.sicop import BASE, HEADERS, RUBROS, SicopClient, SourceError

LISTING = "/bid/api/v1/public/epCartel/searchEpCartelsByPpsType"
DETAIL = "/bid/api/v1/public/epCartel/findPublishedById"
LINES = "/bid/api/v1/public/epCartelProd/findByEpCartelId"
FILES = "/bid/api/v1/public/epCartelFile/getCartelFilesById"
SIGNED_URL = "/comn/api/v1/public/comnFile/downloadWithPAR"
STORAGE_HOST = "objectstorage.us-ashburn-1.oraclecloud.com"
OFFICE_HOURS = range(6, 19)


def page(filters, size):
    return {
        "pageNumber": 0,
        "pageSize": size,
        "tableSorter": {"sorter": "", "order": "desc"},
        "tableFilters": [],
        "formFilters": [{"field": k, "value": v} for k, v in filters.items()],
    }


def server_time():
    response = httpx.head(BASE + LISTING, headers=HEADERS, timeout=20)
    return parsedate_to_datetime(response.headers["date"]).astimezone(UTC).isoformat()


def sequence_chain(client, cartel_no, limit=5):
    chain = []
    for number in range(limit):
        sequence = f"{number:02d}"
        try:
            detail = client.post(DETAIL, {"cartelNo": cartel_no, "cartelSeq": sequence})
        except SourceError:
            break  # Una secuencia inexistente responde HTTP 401.
        chain.append(
            {
                "sequence": sequence,
                "previous": detail.get("preCartelSeq"),
                "version": detail.get("cartelVersion"),
                "modified": detail.get("cartelModYn"),
                "status": detail.get("cartelStatStr"),
            }
        )
    return chain


def classify(path):
    reader = PdfReader(path)
    texts = [len((p.extract_text() or "").strip()) for p in reader.pages[:30]]
    scanned = sum(n < 40 for n in texts)  # Mismo umbral que extractor.py para pedir OCR.
    kind = "digital" if not scanned else "escaneado" if scanned == len(texts) else "mixto"
    return kind, len(reader.pages)


def annexes(tenders, limit, settings):
    found = []
    with tempfile.TemporaryDirectory(prefix="nexo-probe-") as directory:
        for cartel_no in tenders:
            for ref in metadata_get(FILES, {"cartelNo": cartel_no, "cartelSeq": "00"}):
                if len(found) >= limit:
                    return found
                name = ref.get("serverFileNm", "")
                entry = {"cartelNo": cartel_no, "extension": name.rsplit(".", 1)[-1].lower()}
                location = metadata_get(
                    SIGNED_URL,
                    {"fileUrl": (ref["fileServerPath"].rstrip("/") + "/" + name).lstrip("/")},
                    text=True,
                )
                url = urlsplit(location)
                bucket = re.search(r"/n/([^/]+)/b/([^/]+)/o/", url.path)
                entry |= {
                    "host": url.hostname,
                    "namespace": bucket.group(1) if bucket else None,
                    "bucket": bucket.group(2) if bucket else None,
                    "object_matches_reference": name in url.path,
                }
                target = Path(directory) / hashlib.sha256(name.encode()).hexdigest()
                try:
                    metadata = download(location, target, settings)
                    entry |= {"media_type": metadata["media_type"], "bytes": metadata["size"]}
                    if metadata["media_type"] == "application/pdf":
                        entry["kind"], entry["pages"] = classify(target)
                except DocumentError as exc:
                    entry["error"] = str(exc)
                found.append(entry)
                time.sleep(0.5)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-category", type=int, default=50)
    parser.add_argument("--details", type=int, default=12)
    parser.add_argument("--annexes", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("artifacts/sicop-probe.json"))
    args = parser.parse_args()

    client = SicopClient(delay=0.6)
    started = datetime.now(UTC).isoformat()
    report = {"started_at": started, "server_date": server_time(), "source": BASE}
    listings = []
    for category, code in RUBROS.items():
        rows = client.post(LISTING, page({"ppsType": code}, args.per_category))["content"]
        listings += [dict(row, _category=category) for row in rows]

    hours = collections.Counter(datetime.fromisoformat(r["regDt"]).hour for r in listings)
    numbers = [r["cartelNo"] for r in listings]
    procedures = [r["instCartelNo"] for r in listings]
    report["listing"] = {
        "endpoint": LISTING,
        "count": len(listings),
        "by_category": collections.Counter(r["_category"] for r in listings),
        "sequences": collections.Counter(r["cartelSeq"] for r in listings),
        "unique_cartel_no": len(set(numbers)) == len(numbers),
        "unique_procedure": len(set(procedures)) == len(procedures),
        "cartel_no_format": all(re.fullmatch(r"\d{11}", n) for n in numbers),
        "procedure_format": all(re.fullmatch(r"\d{4}[A-Z]{2}-\d{6}-\d{10}", n) for n in procedures),
        "publication_hours": dict(sorted(hours.items())),
        "share_in_office_hours": round(
            sum(hours[h] for h in OFFICE_HOURS) / max(1, len(listings)), 3
        ),
    }

    details, chains = [], {}
    for row in listings[: args.details]:
        ids = {"cartelNo": row["cartelNo"], "cartelSeq": row["cartelSeq"]}
        detail = client.post(DETAIL, ids)
        lines = client.post(LINES, page(ids, 100))["content"]
        details.append(
            {
                "cartelNo": row["cartelNo"],
                "close": detail.get("biddocEndDt"),
                "version": detail.get("cartelVersion"),
                "modified": detail.get("cartelModYn"),
                "lines": len(lines),
                "units": sorted({str(line.get("prodUnit")) for line in lines}),
                "budget_type": type(detail.get("cartelBudget")).__name__,
            }
        )
        if detail.get("cartelModYn") == "Y" and len(chains) < 3:
            chains[row["cartelNo"]] = sequence_chain(client, row["cartelNo"])
    closes = [datetime.fromisoformat(d["close"]) for d in details if d["close"]]
    report["details"] = {
        "endpoints": [DETAIL, LINES],
        "items": details,
        "close_hours": dict(sorted(collections.Counter(c.hour for c in closes).items())),
        "modified_sequence_chains": chains,
    }

    settings = SimpleNamespace(
        document_hosts=f"www.sicop.go.cr,prod-api.sicop.go.cr,{STORAGE_HOST}",
        document_max_bytes=20 * 1024 * 1024,
    )
    found = annexes([d["cartelNo"] for d in details], args.annexes, settings)
    report["annexes"] = {
        "endpoints": [FILES, SIGNED_URL],
        "items": found,
        "kinds": collections.Counter(a.get("kind", a.get("error", "otro")) for a in found),
        "hosts": collections.Counter(a["host"] for a in found),
        "buckets": collections.Counter(f"{a['namespace']}/{a['bucket']}" for a in found),
    }
    report["finished_at"] = datetime.now(UTC).isoformat()
    client.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {
        "consulta": report["started_at"],
        "concursos": report["listing"]["count"],
        "en_horario_de_oficina": report["listing"]["share_in_office_hours"],
        "anexos": report["annexes"]["kinds"],
        "buckets": report["annexes"]["buckets"],
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
