"""Revalidar una apertura pública sin MongoDB ni originales/proveedores en el reporte."""

import argparse
import json
from pathlib import Path

from nexolicitcr.history import fetch_offers
from nexolicitcr.sicop import SourceError
from nexolicitcr.storage import utcnow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cartel_no")
    parser.add_argument("--sequence", default="00")
    parser.add_argument("--lot", default="1")
    parser.add_argument("--output", type=Path, default=Path("artifacts/history-probe.json"))
    args = parser.parse_args()
    report = {
        "started_at": utcnow().isoformat(),
        "cartel_no": args.cartel_no,
        "sequence": args.sequence,
        "lot": args.lot,
    }
    try:
        observed = fetch_offers(args.cartel_no, args.sequence, args.lot)
    except (SourceError, ValueError) as exc:
        report.update(status="unavailable", error_code=str(exc))
        exit_code = 1
    else:
        offers = observed.pop("offers")
        report.update(observed)
        report.update(
            status="validated",
            count=len(offers),
            normalized_prices=sum(o["price_presented"] is not None for o in offers),
            currencies=sorted({o["currency"] for o in offers if o["currency"]}),
            awards_inferred=False,
        )
        exit_code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
