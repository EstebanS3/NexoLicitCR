"""Editable deterministic suggestions; no inferred eligibility or external AI calls."""

import re

from .matching import normalized

SUGGESTIONS_VERSION = "guided-v2"
# Deliberately narrow phrases: an ambiguous "redes" is not an IT service.
VOCABULARY = [
    (
        ("redes informáticas", "redes de datos", "cableado estructurado"),
        ["redes informáticas", "redes de datos", "cableado estructurado"],
    ),
    (
        ("soporte técnico", "mantenimiento informático"),
        ["soporte técnico", "mantenimiento informático"],
    ),
    (("redes sociales",), ["redes sociales"]),
    (("publicidad", "marketing"), ["publicidad", "marketing"]),
    (
        ("software", "aplicaciones web", "desarrollo web"),
        ["software", "aplicaciones web", "desarrollo web"],
    ),
    (("limpieza", "aseo"), ["limpieza", "aseo"]),
    (("desinfección",), ["desinfección"]),
    (("construcción", "remodelación"), ["construcción", "remodelación"]),
    (("alimentos", "alimentación", "catering"), ["alimentación", "catering", "alimentos"]),
    (("jardinería", "jardines"), ["jardinería", "mantenimiento de zonas verdes"]),
    (("muebles", "mobiliario"), ["mobiliario", "muebles"]),
]


def suggest(activity):
    from .matching import contains

    # Conservative clause-level negation, not a general Spanish language parser.
    clauses = re.split(r"[.;,!\n]|\b(?:pero|aunque|sin embargo)\b", normalized(activity))
    positive, negative = [], []
    for clause in clauses:
        parts = re.split(r"\b(?:no|sin|excepto|excluyendo)\b", clause, maxsplit=1)
        positive.append(parts[0])
        if len(parts) > 1:
            negative.append(parts[1])
    terms = []
    for triggers, suggestions in VOCABULARY:
        if any(contains(clause, trigger) for clause in positive for trigger in triggers):
            terms.extend(suggestions)
    # Unknown activities require manual terms, never guesses from locations/adjectives.
    return list(
        dict.fromkeys(
            term for term in terms if not any(contains(clause, term) for clause in negative)
        )
    )[:8]


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
