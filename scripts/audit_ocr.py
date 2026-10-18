"""Reproducible synthetic OCR benchmark across every commercial sector.

Uses the production extractor in an isolated subprocess. Does not contact SICOP,
read MongoDB, or infer quality percentages for real tenders. Reports recovery of
known phrases, not human-validated classification accuracy.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from nexolicitcr.matching import contains
from nexolicitcr.sectors import SECTORS


def digital_page(path, lines, width=816, height=1056):
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=height)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = bytearray(b"BT /F1 16 Tf 40 1000 Td 26 TL\n")
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.extend(("(" + escaped + ") Tj T*\n").encode("cp1252"))
    content.extend(b"ET")
    stream = DecodedStreamObject()
    stream.set_data(bytes(content))
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def fixture(directory, sector, terms, mode):
    path = directory / f"{sector}-{mode}"
    lines = ["REQUISITOS TECNICOS DEL CONCURSO", "Productos y servicios solicitados:"]
    lines += [line for term in terms for line in textwrap.wrap(term, 62)]
    if mode == "digital":
        path = path.with_suffix(".pdf")
        digital_page(path, lines)
        return path
    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)
    font = None
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "Arial.ttf",
        "DejaVuSans.ttf",
    ]:
        try:
            font = ImageFont.truetype(candidate, size=40)
            break
        except OSError:
            pass
    if font is None:
        raise RuntimeError("Install Arial or DejaVu Sans to render Spanish benchmark fixtures.")
    for i, line in enumerate(lines):
        draw.text((85, 220 + i * 70), line, fill="black", font=font)
    if mode == "rotated":
        image = image.rotate(90, expand=True)
    elif mode == "skewed":
        image = image.rotate(3, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="white")
    elif mode == "low_resolution":
        image = image.resize((850, 1100), Image.Resampling.LANCZOS)
    if mode in {"scan", "mixed"}:
        path = path.with_suffix(".pdf")
        image.save(path, "PDF", resolution=150)
        if mode == "mixed":
            heading = directory / "heading.pdf"
            digital_page(
                heading, ["Encabezado digital de referencia para este expediente institucional."]
            )
            writer = PdfWriter()
            page = PdfReader(path).pages[0]
            page.merge_page(PdfReader(heading).pages[0])
            writer.add_page(page)
            writer.write(path)
    else:
        path = path.with_suffix(".jpg" if mode == "jpeg" else ".png")
        image.save(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("artifacts/ocr-audit.json"))
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["digital", "png", "jpeg", "scan", "mixed", "rotated", "skewed", "low_resolution"],
        default=["digital", "png", "jpeg", "scan", "mixed", "rotated", "skewed", "low_resolution"],
    )
    args = parser.parse_args()
    results = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="nexo-ocr-audit-") as temp:
        directory = Path(temp)
        for sector, data in SECTORS.items():
            if sector == "other":
                continue
            terms = [entry[1][0] for entry in data["specialties"].values() if entry[1]]
            for mode in args.modes:
                source = fixture(directory, sector, terms, mode)
                output = directory / "result.json"
                before = time.monotonic()
                process = subprocess.run(  # noqa: S603 -- fixed interpreter/module and local fixture paths
                    [
                        sys.executable,
                        "-m",
                        "nexolicitcr.extractor",
                        str(source),
                        str(output),
                        "--pages",
                        "2",
                    ],
                    capture_output=True,
                    timeout=125,
                    env=os.environ.copy(),
                )
                pages = json.loads(output.read_text()) if process.returncode == 0 else []
                text = "\n".join(page["text"] for page in pages)
                recovered = [term for term in terms if contains(text, term)]
                row = {
                    "sector": sector,
                    "mode": mode,
                    "expected_terms": terms,
                    "recovered_terms": recovered,
                    "missed_terms": [t for t in terms if t not in recovered],
                    "errors": [p["error"] for p in pages if p["error"]],
                    "methods": [p["method"] for p in pages],
                    "exit_code": process.returncode,
                    "seconds": round(time.monotonic() - before, 2),
                }
                results.append(row)
            print(
                f"{sector}: "
                + ", ".join(
                    f"{r['mode']}={len(r['recovered_terms'])}/{len(terms)}"
                    for r in results
                    if r["sector"] == sector
                ),
                flush=True,
            )
    report = {
        "kind": "synthetic-known-phrase-recovery",
        "seconds": round(time.monotonic() - started, 2),
        "sectors": len({r["sector"] for r in results}),
        "cases": len(results),
        "expected": sum(len(r["expected_terms"]) for r in results),
        "recovered": sum(len(r["recovered_terms"]) for r in results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))


if __name__ == "__main__":
    main()
