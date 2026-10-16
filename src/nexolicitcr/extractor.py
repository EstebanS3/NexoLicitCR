"""Isolated PDF/image extraction process; never imported into the HTTP request loop."""

import argparse
import json
import resource
import shutil
import subprocess
import tempfile
from pathlib import Path

VERSION = "pdf-ocr-v1"


def run_command(args, timeout=30):
    subprocess.run(  # noqa: S603 -- fixed executables and argument lists, never a shell
        args, check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def ocr(image, target):
    executable = shutil.which("tesseract")
    if not executable:
        raise RuntimeError("OCR_UNAVAILABLE")
    run_command([executable, str(image), str(target), "-l", "spa", "--psm", "3"])
    return target.with_suffix(".txt").read_text()[:100000]


def extract(path, max_pages):
    from PIL import Image
    from pypdf import PdfReader

    Image.MAX_IMAGE_PIXELS = 20_000_000
    pages = []
    with tempfile.TemporaryDirectory(prefix="nexo-extract-") as directory:
        temp = Path(directory)
        if path.read_bytes()[:5] == b"%PDF-":
            reader = PdfReader(path, strict=True)
            if reader.is_encrypted or len(reader.pages) > max_pages:
                raise ValueError("PDF_LIMIT_OR_ENCRYPTED")
            for index, page in enumerate(reader.pages):
                text = (page.extract_text() or "").strip()[:100000]
                method, error = "digital", None
                if len(text) < 40:
                    renderer = shutil.which("pdftoppm")
                    if not renderer:
                        error = "PDF_RENDERER_UNAVAILABLE"
                    else:
                        try:
                            output = temp / f"page-{index}"
                            run_command(
                                [
                                    renderer,
                                    "-f",
                                    str(index + 1),
                                    "-l",
                                    str(index + 1),
                                    "-scale-to",
                                    "2400",
                                    "-singlefile",
                                    "-png",
                                    str(path),
                                    str(output),
                                ]
                            )
                            text = ocr(output.with_suffix(".png"), temp / f"ocr-{index}")
                            method = "ocr"
                        except (RuntimeError, subprocess.SubprocessError):
                            error = "OCR_FAILED_OR_UNAVAILABLE"
                pages.append(
                    {
                        "page": index + 1,
                        "text": text,
                        "method": method,
                        "error": error,
                        "extractor_version": VERSION,
                    }
                )
        else:
            with Image.open(path) as image:
                if (
                    image.format not in {"PNG", "JPEG"}
                    or image.width * image.height > Image.MAX_IMAGE_PIXELS
                ):
                    raise ValueError("IMAGE_LIMIT_OR_FORMAT")
                image.convert("RGB").save(temp / "image.png")
            try:
                text, error = ocr(temp / "image.png", temp / "ocr"), None
            except (RuntimeError, subprocess.SubprocessError):
                text, error = "", "OCR_FAILED_OR_UNAVAILABLE"
            pages.append(
                {
                    "page": 1,
                    "text": text,
                    "method": "ocr",
                    "error": error,
                    "extractor_version": VERSION,
                }
            )
    return pages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--pages", type=int, default=30)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (110, 115))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    import sys

    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    result = extract(Path(args.input), args.pages)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
