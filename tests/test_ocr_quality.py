"""Category-independent extraction and evidence regressions; synthetic examples."""

import subprocess
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image
from pypdf import PdfWriter

from nexolicitcr import extractor
from nexolicitcr.discovery import matching_catalog
from nexolicitcr.documents import metadata_get
from nexolicitcr.matching import score
from nexolicitcr.models import CompanyProfile
from nexolicitcr.sectors import SECTORS, specialty_terms
from nexolicitcr.sicop import SourceRateLimited


@pytest.mark.parametrize(
    "sector,specialty",
    [(s, k) for s, data in SECTORS.items() for k in data["specialties"] if s != "other"],
)
def test_every_specialty_can_match_only_ocr_evidence_and_preserves_source(sector, specialty):
    terms = specialty_terms(sector, specialty)
    profile = CompanyProfile(
        sector=sector,
        specialty=specialty,
        activity="Ofrecemos servicios para instituciones",
        services=terms,
    )
    text = f"Objeto contractual:\n{terms[0].upper()} para la institución."
    page = {"text": text, "method": "ocr", "page": 3, "document_id": "scan-1"}
    result = score(
        {"title": "Contratación institucional", "lines": []},
        matching_catalog({"profile": profile.model_dump(), "items": []}),
        [page],
    )
    assert result["score"] > 0
    reason = result["products"][0]["reasons"][0]
    assert reason["document_id"] == "scan-1" and reason["page"] == 3
    assert reason["method"] == "ocr" and reason["fragment"] in text


@pytest.mark.parametrize(
    "term,broken",
    [
        ("ciberseguridad", "ciberseguri-\ndad"),
        ("alimentación", "alimenta-\nción"),
        ("pavimentación", "pavimen-\ntación"),
        ("insumos médicos", "insumos\u00a0\n  médicos"),
    ],
)
def test_ocr_line_wrapping_matches_and_fragment_points_to_actual_evidence(term, broken):
    text = "Contexto previo. " * 30 + broken + " para instituciones públicas."
    result = score(
        {"title": "Consulta", "lines": []},
        {"items": [{"id": "x", "name": term, "keywords": [term], "active": True}]},
        [{"text": text, "method": "ocr", "page": 1}],
    )
    assert result["score"] > 0
    assert broken in result["products"][0]["reasons"][0]["fragment"]


def test_sparse_digital_heading_does_not_hide_scanned_body():
    page = {
        "/Resources": {
            "/XObject": SimpleNamespace(
                get_object=lambda: {
                    "/Im1": SimpleNamespace(
                        get_object=lambda: {"/Subtype": "/Image", "/Width": 1600, "/Height": 2200}
                    )
                }
            )
        }
    }
    assert extractor.needs_ocr(page, "Encabezado digital que tiene más de cuarenta caracteres.")
    assert not extractor.needs_ocr(page, "Contenido digital extenso. " * 30)
    assert not extractor.needs_ocr(
        {}, "Texto digital suficiente sin imágenes que requieran reconocimiento."
    )


def test_spanish_missing_is_distinct_from_missing_binary(monkeypatch):
    extractor.ocr_executable.cache_clear()
    monkeypatch.setattr(extractor.shutil, "which", lambda _: "/test/tesseract")
    monkeypatch.setattr(
        extractor.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(stdout="List of available languages (1):\neng\n"),
    )
    with pytest.raises(RuntimeError, match="OCR_SPANISH_UNAVAILABLE"):
        extractor.ocr_executable()
    extractor.ocr_executable.cache_clear()


def test_renderer_missing_preserves_digital_heading_and_marks_partial(tmp_path, monkeypatch):
    from test_documents_history import digital_pdf

    path = tmp_path / "hybrid.pdf"
    digital_pdf(path)
    monkeypatch.setattr(extractor, "needs_ocr", lambda *args: True)
    monkeypatch.setattr(extractor.shutil, "which", lambda _: None)
    page = extractor.extract(path, 2)[0]
    assert page["error"] == "PDF_RENDERER_UNAVAILABLE"
    assert "soporte de redes" in page["text"]


def test_ocr_timeout_and_empty_results_are_explicit(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(path)
    monkeypatch.setattr(
        extractor,
        "ocr",
        lambda *args: (_ for _ in ()).throw(subprocess.TimeoutExpired("tesseract", 30)),
    )
    assert extractor.extract(path, 1)[0]["error"] == "OCR_FAILED_OR_UNAVAILABLE"
    monkeypatch.setattr(
        extractor, "ocr", lambda *args: (_ for _ in ()).throw(RuntimeError("OCR_EMPTY"))
    )
    assert extractor.extract(path, 1)[0]["error"] == "OCR_EMPTY"


def test_encrypted_pdf_never_appears_as_successful_empty_document(tmp_path):
    path = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("private-password-for-test")
    writer.write(path)
    with pytest.raises(ValueError, match="PDF_LIMIT_OR_ENCRYPTED"):
        extractor.extract(path, 30)


def test_document_metadata_rate_limit_reaches_job_backoff(monkeypatch):
    import nexolicitcr.documents as documents

    real_client = httpx.Client
    monkeypatch.setattr(
        documents.httpx,
        "Client",
        lambda **kw: real_client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(429, headers={"retry-after": "600"})
            )
        ),
    )
    with pytest.raises(SourceRateLimited) as caught:
        metadata_get("/files", {})
    assert caught.value.retry_after == 600


@pytest.mark.parametrize(
    "title",
    [
        "CONSTRUCCIÓN DE LA ESTRUCTURA DE PAVIMENTO EN CALLE RÍO SEGUNDO",
        "Suministro y colocación de mezcla asfáltica en caliente",
        "Conformación, colocación y compactación de material granular",
        "Suministro y colocación de concreto permeable premezclado",
        "Servicio de rehabilitación vial",
    ],
)
def test_real_public_road_phrases_are_explained_without_matching_material_sales(title):
    item = {
        "id": "road",
        "name": "Obra vial",
        "active": True,
        "keywords": specialty_terms("construction", "roads"),
    }
    result = score({"title": title, "lines": [], "category": "obras"}, {"items": [item]})
    assert result["score"] > 0
    assert any(
        reason["term"].lower() in title.lower() for reason in result["products"][0]["reasons"]
    )
    assert (
        score({"title": title, "lines": [], "category": "bienes"}, {"items": [item]})["score"] == 0
    )


def test_metadata_network_failure_is_a_controlled_source_error(monkeypatch):
    import nexolicitcr.documents as documents

    real_client = httpx.Client

    def fail(request):
        raise httpx.ConnectTimeout("test timeout")

    monkeypatch.setattr(
        documents.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(fail))
    )
    with pytest.raises(documents.DocumentError, match="DOCUMENT_METADATA_NETWORK_FAILED"):
        metadata_get("/files", {})


def test_other_incomplete_documents_keep_available_evidence_preliminary():
    result = score(
        {"title": "Consulta", "lines": []},
        {"items": []},
        [{"text": "Página digital leída correctamente", "method": "digital", "page": 1}],
        incomplete_documents=True,
    )
    assert result["preliminary"]


def test_current_failed_or_omitted_annex_invalidates_complete_radar(store, settings):
    from test_cache_matching import tender_payload

    from nexolicitcr.cache import OptionalCache
    from nexolicitcr.matching import Radar

    tender = tender_payload()
    store.db.tenders.insert_one({"_id": "test:quality", "payload": tender, "hash": "v1"})
    store.db.documents.insert_one(
        {
            "_id": "ready",
            "tender_key": "test:quality",
            "source_identity": "ref-ready",
            "sha256": "ready-hash",
            "state": "ready",
            "current": True,
        }
    )
    store.db.extracted_pages.insert_one(
        {"document_id": "ready", "text": "texto digital", "method": "digital", "page": 1}
    )
    radar = Radar(store, OptionalCache(settings))
    assert not radar.rows()[0]["match"]["preliminary"]
    store.db.documents.insert_one(
        {
            "_id": "omitted",
            "tender_key": "test:quality",
            "source_identity": "ref-omitted",
            "sha256": "",
            "state": "omitted",
            "current": True,
        }
    )
    assert radar.rows()[0]["match"]["preliminary"]
    store.db.documents.update_one({"_id": "omitted"}, {"$set": {"current": False}})
    assert not radar.rows()[0]["match"]["preliminary"]


def test_over_limit_pdf_keeps_bounded_evidence_and_marks_remainder(tmp_path):
    from pypdf import PdfReader
    from test_documents_history import digital_pdf

    first = tmp_path / "first.pdf"
    digital_pdf(first)
    writer = PdfWriter()
    for _ in range(3):
        writer.add_page(PdfReader(first).pages[0])
    source = tmp_path / "long.pdf"
    writer.write(source)
    pages = extractor.extract(source, 2)
    assert len(pages) == 2
    assert all("soporte de redes" in page["text"] for page in pages)
    assert pages[0]["error"] is None
    assert pages[1]["error"] == "PAGE_COUNT_LIMIT"
    assert score({"title": "Consulta", "lines": []}, {"items": []}, pages)["preliminary"]


def test_orientation_model_missing_is_explicit(monkeypatch):
    extractor.ocr_executable.cache_clear()
    monkeypatch.setattr(extractor.shutil, "which", lambda _: "/test/tesseract")
    monkeypatch.setattr(
        extractor.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="spa\n")
    )
    with pytest.raises(RuntimeError, match="OCR_ORIENTATION_UNAVAILABLE"):
        extractor.ocr_executable()
    extractor.ocr_executable.cache_clear()


def test_document_metadata_respects_configured_request_delay(store, settings, monkeypatch):
    from nexolicitcr.documents import DocumentService

    times = iter([10.0, 10.5, 12.0])
    sleeps = []
    monkeypatch.setattr("nexolicitcr.documents.time.monotonic", lambda: next(times))
    monkeypatch.setattr("nexolicitcr.documents.time.sleep", sleeps.append)
    monkeypatch.setattr("nexolicitcr.documents.metadata_get", lambda *args: [])
    service = DocumentService(store, settings)
    service._metadata("/files", {})
    service._metadata("/url", {})
    assert sleeps == [1.5]


def test_unreadable_pdf_text_layer_falls_back_to_ocr(tmp_path, monkeypatch):
    from pypdf import PageObject
    from pypdf.errors import PdfReadError
    from test_documents_history import digital_pdf

    source = tmp_path / "broken-font.pdf"
    digital_pdf(source)

    def broken(*args, **kwargs):
        raise PdfReadError("Broken text layer")

    monkeypatch.setattr(PageObject, "extract_text", broken)
    monkeypatch.setattr(extractor.shutil, "which", lambda _: "/test/pdftoppm")
    monkeypatch.setattr(extractor, "run_command", lambda *args: None)
    monkeypatch.setattr(
        extractor, "ocr", lambda *args: "Suministro de insumos médicos para instituciones"
    )
    page = extractor.extract(source, 1)[0]
    assert page["method"] == "ocr" and page["error"] is None
    assert "insumos médicos" in page["text"]


def test_empty_pdf_is_not_successful_empty_evidence(tmp_path):
    source = tmp_path / "empty.pdf"
    PdfWriter().write(source)
    with pytest.raises(ValueError, match="PDF_EMPTY"):
        extractor.extract(source, 1)
