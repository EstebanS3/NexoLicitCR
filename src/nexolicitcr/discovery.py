"""Editable deterministic suggestions; no inferred eligibility or external AI calls."""

import re

from .matching import normalized

SUGGESTIONS_VERSION = "guided-v1"
VOCABULARY = [
    (
        ("redes", "informatica", "tecnologia"),
        ["redes", "soporte técnico", "mantenimiento informático"],
    ),
    (("limpieza", "aseo"), ["limpieza", "aseo", "desinfección"]),
    (
        ("construccion", "remodelacion"),
        ["construcción", "remodelación", "mantenimiento de edificios"],
    ),
    (
        ("alimentos", "alimentacion", "catering"),
        ["alimentación", "catering", "preparación de alimentos"],
    ),
    (("jardineria", "jardines"), ["jardinería", "mantenimiento de zonas verdes"]),
    (("muebles", "mobiliario"), ["mobiliario", "muebles de oficina"]),
]
STOP = set(
    "somos empresa ofrecemos servicios generales hacemos dedicada dedicamos nuestro nuestra para desde hasta como instalamos mantenemos vendemos servicio una unos unas los las del con por que hacemos tenemos".split()
)


def suggest(activity):
    text = normalized(activity)
    terms = []
    for triggers, suggestions in VOCABULARY:
        if any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text) for t in triggers):
            terms.extend(suggestions)
    if not terms:
        terms = [word for word in re.findall(r"[a-z]{4,}", text) if word not in STOP]
    return list(dict.fromkeys(terms))[:8]


def matching_catalog(catalog):
    profile = catalog.get("profile")
    if not profile:
        return catalog
    item = {
        "id": "confirmed-profile",
        "name": "Actividad de tu empresa",
        "active": True,
        "keywords": profile["services"],
        "exclusions": profile["exclusions"],
    }
    return {**catalog, "items": [*catalog["items"], item]}
