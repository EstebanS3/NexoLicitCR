"""Isolated PDF/image extraction process; never imported into the HTTP request loop."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

VERSION = "pdf-ocr-v2"


def run_command(args, timeout=30):
    subprocess.run(  # noqa: S603 -- fixed executables and argument lists, never a shell
        args, check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


@lru_cache(maxsize=1)
def ocr_executable():
    executable = shutil.which("tesseract")
    if not executable:
        raise RuntimeError("OCR_UNAVAILABLE")
    languages = subprocess.run(  # noqa: S603 -- fixed executable, no shell
        [executable, "--list-langs"], check=True, capture_output=True, text=True, timeout=5
    ).stdout.splitlines()
    if "spa" not in {line.strip() for line in languages}:
        raise RuntimeError("OCR_SPANISH_UNAVAILABLE")
    if "osd" not in {line.strip() for line in languages}:
        raise RuntimeError("OCR_ORIENTATION_UNAVAILABLE")
    return executable


def ocr(image, target):
    executable = ocr_executable()
    # Automatic layout and orientation detection also handles sideways scans.
    run_command([executable, str(image), str(target), "-l", "spa", "--psm", "1"])
    text = target.with_suffix(".txt").read_text(encoding="utf-8").strip()[:100000]
    if not text:
        raise RuntimeError("OCR_EMPTY")
    return text


def needs_ocr(page, text):
    if len(text) < 40:
        return True
    # A searchable heading does not make a scanned body searchable. Inspect image
    # metadata without decoding large image streams in the parent HTTP process.
    resources = page.get("/Resources")
    resources = (
        resources.get_object() if resources and hasattr(resources, "get_object") else resources
    )
    objects = (resources or {}).get("/XObject")
    if len(text) < 250 and objects:
        for ref in objects.get_object().values():
            obj = ref.get_object()
            if (
                obj.get("/Subtype") == "/Image"
                and min(obj.get("/Width", 0), obj.get("/Height", 0)) >= 800
            ):
                return True
    return False


def extract(path, max_pages):
    from PIL import Image
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    Image.MAX_IMAGE_PIXELS = 20_000_000
    if not 1 <= max_pages <= 100:
        raise ValueError("PDF_PAGE_LIMIT_INVALID")
    pages = []
    with tempfile.TemporaryDirectory(prefix="nexo-extract-") as directory:
        temp = Path(directory)
        if path.read_bytes()[:5] == b"%PDF-":
            reader = PdfReader(path, strict=True)
            if reader.is_encrypted:
                raise ValueError("PDF_LIMIT_OR_ENCRYPTED")
            if not len(reader.pages):
                raise ValueError("PDF_EMPTY")
            for index, page in enumerate(reader.pages[:max_pages]):
                try:
                    text = (page.extract_text() or "").strip()[:100000]
                except (PdfReadError, ValueError, TypeError, KeyError, UnicodeError):
                    # Broken text encoding can still have a readable visual page.
                    text = ""
                method, error = "digital", None
                if needs_ocr(page, text):
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
                            recognized = ocr(output.with_suffix(".png"), temp / f"ocr-{index}")
                            if (
                                text
                                and " ".join(text.split()).casefold()
                                not in " ".join(recognized.split()).casefold()
                            ):
                                text = (text + "\n" + recognized).strip()[:100000]
                            else:
                                text = recognized
                            method = "ocr"
                        except RuntimeError as exc:
                            error = str(exc)
                        except (OSError, subprocess.SubprocessError):
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
            if len(reader.pages) > max_pages and pages:
                # Preserve bounded evidence instead of discarding the whole PDF.
                pages[-1]["error"] = pages[-1]["error"] or "PAGE_COUNT_LIMIT"
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
            except RuntimeError as exc:
                text, error = "", str(exc)
            except (OSError, subprocess.SubprocessError):
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


def apply_limits():
    """Apply rlimits where the platform supports them.

    The resource module is Unix-only; on Windows the parent's subprocess timeout is the bound.
    """
    try:
        import resource
    except ImportError:
        return
    resource.setrlimit(resource.RLIMIT_CPU, (110, 115))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--pages", type=int, default=30)
    args = parser.parse_args()
    apply_limits()
    result = extract(Path(args.input), args.pages)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
