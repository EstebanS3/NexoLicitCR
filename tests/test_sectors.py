"""Commercial taxonomy cases are synthetic; they are not SICOP quality labels."""

import pytest

from nexolicitcr.matching import score
from nexolicitcr.models import CompanyProfile
from nexolicitcr.sectors import SECTORS, specialty_terms


def relevance(sector, specialty, title, line=""):
    tender = {
        "title": title,
        "lines": [{"lot": "1", "number": "1", "description": line}] if line else [],
    }
    catalog = {
        "items": [
            {
                "id": "selected-specialty",
                "name": SECTORS[sector]["specialties"][specialty][0],
                "active": True,
                "keywords": specialty_terms(sector, specialty),
            }
        ]
    }
    return score(tender, catalog)["score"]


@pytest.mark.parametrize(
    ("sector", "specialty", "title", "line"),
    [
        (
            "health",
            "medical_supplies",
            "Compra de suministros hospitalarios",
            "GUANTES QUIRÚRGICOS",
        ),
        ("security", "guarding", "Servicio de vigilancia para instalaciones", ""),
        ("transport", "passengers", "Contratación de transporte de personas", ""),
        ("transport", "logistics", "Arrendamiento para operaciones logísticas", ""),
        ("vehicles", "maintenance", "MANTENIMIENTO DE VEHÍCULOS DE LA INSTITUCIÓN", ""),
        ("education", "training", "Curso de certificación técnica", ""),
        ("construction", "buildings", "Obras en el edificio público", "CONSTRUCCION (OBRA CIVIL)"),
        ("construction", "roads", "Construcción de aceras para acceso peatonal", ""),
        ("construction", "water", "Mejoras al alcantarillado pluvial", ""),
        ("construction", "electrical", "Suministro e instalación de luminarias", ""),
        ("construction", "metalwork", "Fabricación de portones para edificio público", ""),
        ("construction", "materials", "Adquisición de MADERA Y PLYWOOD", ""),
        (
            "facilities",
            "cleaning_supplies",
            "Suministros para las instalaciones",
            "LÍQUIDO LIMPIADOR MULTIPROPÓSITO",
        ),
        ("textiles", "protective_clothing", "Equipo de protección personal", ""),
        ("environment", "waste", "Recolección de residuos en instalaciones públicas", ""),
        ("events", "production", "Compra de figuras inflables para evento cultural", ""),
    ],
)
def test_explicit_specialties_match_titles_or_lines(sector, specialty, title, line):
    assert relevance(sector, specialty, title, line) > 0


@pytest.mark.parametrize(
    ("sector", "specialty", "matching_title", "unrelated_title"),
    [
        (
            "technology",
            "networks",
            "Redes informáticas para oficinas",
            "Redes para arcos de fútbol",
        ),
        ("sports", "goal_nets", "Redes para arcos de fútbol", "Redes informáticas para oficinas"),
        ("marketing", "social", "Gestión de redes sociales", "Instalación de redes eléctricas"),
        (
            "construction",
            "electrical",
            "Mantenimiento de redes eléctricas",
            "Gestión de redes sociales",
        ),
        (
            "security",
            "guarding",
            "Servicio de seguridad privada",
            "Servicio de seguridad informática",
        ),
        (
            "technology",
            "cybersecurity",
            "Servicio de seguridad informática",
            "Servicio de seguridad privada",
        ),
        (
            "health",
            "medical_equipment",
            "Mantenimiento de equipo médico",
            "Equipo de protección personal",
        ),
        (
            "textiles",
            "protective_clothing",
            "Equipo de protección personal",
            "Mantenimiento de equipo médico",
        ),
        (
            "facilities",
            "cleaning",
            "Servicio de limpieza de oficinas",
            "Productos de limpieza para oficinas",
        ),
        (
            "facilities",
            "cleaning_supplies",
            "Productos de limpieza para oficinas",
            "Servicio de limpieza de oficinas",
        ),
        ("transport", "passengers", "Transporte de personas", "Transporte de carga"),
        ("transport", "freight", "Transporte de carga", "Transporte de personas"),
        (
            "professional",
            "accounting",
            "Auditoría financiera",
            "Auditoría de seguridad informática",
        ),
    ],
)
def test_similar_words_do_not_cross_commercial_specialties(
    sector, specialty, matching_title, unrelated_title
):
    assert relevance(sector, specialty, matching_title) > 0
    assert relevance(sector, specialty, unrelated_title) == 0


def test_all_specialties_fit_confirmable_profile_without_generic_ambiguous_terms():
    ambiguous = {"redes", "seguridad", "mantenimiento", "servicios", "equipo", "suministros"}
    for sector, data in SECTORS.items():
        for specialty, (label, _) in data["specialties"].items():
            terms = specialty_terms(sector, specialty)
            if (sector, specialty) == ("other", "custom"):
                assert terms == []
                continue
            profile = CompanyProfile(
                sector=sector,
                specialty=specialty,
                activity=f"Ofrecemos {label.lower()}.",
                services=terms,
            )
            assert profile.services
            assert len(terms) == len(set(terms))
            assert not ambiguous.intersection(terms)


def test_original_profile_ids_remain_valid_and_terms_are_editable_copies():
    original = {
        "technology": ("networks", "software", "support"),
        "sports": ("goal_nets", "equipment"),
        "marketing": ("social", "advertising"),
        "facilities": ("cleaning", "gardens"),
        "construction": ("buildings", "electrical"),
        "food": ("catering", "supplies"),
        "furniture": ("office",),
        "other": ("custom",),
    }
    for sector, specialties in original.items():
        for specialty in specialties:
            selected = specialty_terms(sector, specialty)
            expected = selected.copy()
            selected.append("mi servicio específico")
            assert specialty_terms(sector, specialty) == expected
    assert specialty_terms("", "") is None


@pytest.mark.parametrize(
    ("sector", "specialty"),
    [("unknown", "medical_supplies"), ("health", "guarding"), ("health", ""), ("", "guarding")],
)
def test_invalid_or_cross_sector_selection_is_rejected(sector, specialty):
    with pytest.raises(ValueError, match="pertenezca al sector"):
        specialty_terms(sector, specialty)


def test_new_specialty_can_be_previewed_and_saved_without_starting_search(client, store):
    from bs4 import BeautifulSoup

    session = store.session_create("administrator", 8)
    client.cookies.set("nexo_session", session)
    form = {
        "csrf": store.session_get(session)["csrf"],
        "revision": 0,
        "company_name": "Empresa de prueba aislada",
        "sector": "health",
        "specialty": "medical_supplies",
    }
    draft = client.post("/discover/draft", data=form, headers={"origin": "http://localhost:8000"})
    assert draft.status_code == 200
    soup = BeautifulSoup(draft.text, "html.parser")
    assert "insumos médicos" in soup.select_one("[name=services]").text
    assert "profile" not in store.catalog()
    confirm = client.post(
        "/discover/confirm",
        data={
            **form,
            "activity": "Suministramos insumos médicos para instituciones",
            "services": "material de curación",
            "category": "bienes",
            "confirmed": "true",
        },
        headers={"origin": "http://localhost:8000"},
    )
    assert confirm.status_code == 200
    profile = store.catalog()["profile"]
    assert profile["sector"] == "health"
    assert profile["specialty"] == "medical_supplies"
    assert profile["services"] == ["material de curación"]
    assert store.db.jobs.count_documents({}) == 0
