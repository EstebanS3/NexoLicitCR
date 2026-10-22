"""Select reviewed, completed scenes from the private live-demo recordings.

The failed portion after a completed scene is omitted explicitly, never relabeled
as a successful query. Live queue states and documents remain untouched.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "var/demo-sicop-video"


def main():
    prefix = json.loads((WORK / "take-prefix.json").read_text())
    expand = json.loads((WORK / "take-expand.json").read_text())
    resumed = json.loads((WORK / "take-resume.json").read_text())
    if resumed["failed"] or resumed["errors"] or resumed["responses"]:
        raise ValueError("La continuación debe terminar sin incidencias.")
    decisions = json.loads((WORK / "take-decisions.json").read_text())
    if decisions["failed"] or decisions["errors"] or decisions["responses"]:
        raise ValueError("La toma final de decisiones debe terminar sin incidencias.")
    parts = {"prefix": prefix, "expand": expand, "resume": resumed, "decisions": decisions}
    selected = {
        "prefix": [
            f"{i:02}-{name}"
            for i, name in enumerate(
                [
                    "cuenta",
                    "empresa",
                    "especialidad",
                    "perfil",
                    "catalogo",
                    "consulta",
                    "espera-sicop",
                ],
                1,
            )
        ],
        "expand": ["08-ampliar"],
        "resume": [
            event["id"]
            for event in resumed["events"]
            if event["id"].split("-")[0] not in {"14", "15", "16", "17", "18"}
        ],
        "decisions": [event["id"] for event in decisions["events"]],
    }
    events = []
    for key, ids in selected.items():
        take = parts[key]
        if take["errors"] or take["responses"]:
            raise ValueError("Revisar incidencias de navegador antes de seleccionar escenas.")
        for scene_id in ids:
            event = next(row for row in take["events"] if row["id"] == scene_id)
            if not event.get("end") or not event.get("actionEnd"):
                raise ValueError("No incluir una escena interrumpida.")
            events.append({**event, "take": key})
    manifest = {
        "takes": {
            key: {
                "videoPath": value["videoPath"],
                "end": value["end"],
                "recordedAt": value["recordedAt"],
            }
            for key, value in parts.items()
        },
        "events": events,
        "failed": None,
        "errors": [],
        "responses": [],
        "recordedAt": decisions["recordedAt"],
        "mainJob": prefix["mainJob"],
        "docsJob": resumed["docsJob"],
        "production_cuts": [
            "Las decisiones finales se repiten con la nota corregida: el PDF principal está listo; los archivos incompatibles pertenecen a otros concursos.",
            "Se retienen registro, perfil y consulta inicial completa; se omite la espera de un selector que ya no estaba en los diez recientes.",
            "Se retiene la ampliación real; se retoma el mismo trabajo después de un corte de conexión local. Se omite el intervalo de producción entre capturas.",
        ],
    }
    (WORK / "recording.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Manifiesto revisado: {len(events)} escenas de la misma empresa y base.")


if __name__ == "__main__":
    main()
