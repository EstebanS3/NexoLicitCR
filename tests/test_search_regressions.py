"""Synthetic business descriptions and navigation regressions, without touching local data."""

import pytest
from test_cache_matching import tender_payload
from test_discovery import authenticated

from nexolicitcr.discovery import suggest
from nexolicitcr.matching import contains
from nexolicitcr.models import CompanyProfile


@pytest.mark.parametrize(
    ("activity", "expected", "absent"),
    [
        ("Gestionamos redes sociales y publicidad", "redes sociales", "soporte técnico"),
        ("Instalamos redes informáticas para oficinas", "redes informáticas", "redes sociales"),
        ("Desarrollamos software y aplicaciones web", "software", "limpieza"),
        ("No ofrecemos limpieza. Desarrollamos software", "software", "limpieza"),
        ("Hacemos jardinería pero no limpieza ni aseo", "jardinería", "limpieza"),
    ],
)
def test_business_descriptions(activity, expected, absent):
    result = suggest(activity)
    assert expected in result
    assert absent not in result


def test_ambiguous_or_unknown_description_does_not_invent_services():
    assert suggest("Somos una empresa de redes") == []
    assert suggest("Somos una empresa excelente ubicada en Heredia") == []


@pytest.mark.parametrize(
    ("text", "term", "expected"),
    [
        ("Redes informáticas", "red informática", True),
        ("Muebles de oficina", "mueble de oficina", True),
        ("Mantenimiento de redes sociales", "red informática", False),
        ("Desinfección de edificios", "infección", False),
        ("Adquisición de software", "", False),
    ],
)
def test_controlled_plural_matching(text, term, expected):
    assert contains(text, term) == expected


def test_default_radar_hides_unrelated_but_preserves_explicit_browsing(client, store):
    authenticated(client, store)
    store.save_profile(
        CompanyProfile(activity="Servicios de jardinería", services=["jardinería"]), 0
    )
    for key, title in [("relevant", "Jardinería municipal"), ("unrelated", "Software contable")]:
        tender = tender_payload()
        tender["title"] = title
        tender["lines"] = []
        store.db.tenders.insert_one({"_id": key, "payload": tender, "hash": key})
    page = client.get("/opportunities")
    assert "Jardinería municipal" in page.text
    assert "Software contable" not in page.text
    assert "Software contable" in client.get("/opportunities?minimum=0").text
    assert "Jardinería municipal" in client.get("/opportunities?q=jardineria").text
    store.db.decisions.insert_one(
        {"company": "company", "tender_key": "unrelated", "status": "following"}
    )
    assert "Software contable" in client.get("/opportunities?status=following").text
