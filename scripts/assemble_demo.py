"""Combine the recorded application, local narration and Spanish subtitles.

Optional media tooling only. Pass --ffmpeg with a trusted local FFmpeg binary.
The application itself does not require FFmpeg, Node.js or a speech synthesizer.
"""

import argparse
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    args = parser.parse_args()
    if not args.ffmpeg or not Path(args.ffmpeg).is_file():
        parser.error("Indicar --ffmpeg RUTA a un ejecutable local.")
    ffmpeg = str(Path(args.ffmpeg).resolve())
    work = ROOT / "var/demo-video"
    recording = json.loads((work / "recording.json").read_text())
    if recording["errors"] or recording["responses"]:
        raise SystemExit("La grabación contiene incidencias; revisar antes de editar.")
    if any(abs(event["actualStart"] - event["targetStart"]) > 3 for event in recording["events"]):
        raise SystemExit("Las escenas están desincronizadas; repetir la grabación completa.")
    video = Path(recording["videoPath"]).resolve()
    if not video.is_relative_to(work / "raw"):
        raise SystemExit("El video fuente debe pertenecer a var/demo-video/raw.")
    audio = work / "audio/narracion.wav"
    with wave.open(str(audio), "rb") as source:
        duration = source.getnframes() / source.getframerate()
    probe = subprocess.run(  # noqa: S603 -- explicit local media executable and file
        [ffmpeg, "-hide_banner", "-i", str(video)], capture_output=True, text=True
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if not match:
        raise SystemExit("No se pudo medir el video fuente.")
    hours, minutes, seconds = map(float, match.groups())
    raw_duration = hours * 3600 + minutes * 60 + seconds
    lead = max(0.0, raw_duration - duration)
    if not 180 <= duration <= 300 or lead > 15:
        raise SystemExit("Duración o sincronización fuera de los límites de la demo.")
    output = ROOT / "docs/entrega/demo/NexoLicitCR_demo.mp4"
    subtitles = ROOT / "docs/entrega/demo/NexoLicitCR_demo.srt"
    command = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        str(lead),
        "-i",
        str(video),
        "-i",
        str(audio),
        "-i",
        str(subtitles),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-map",
        "2:0",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-c:s",
        "mov_text",
        "-metadata:s:a:0",
        "language=spa",
        "-metadata:s:s:0",
        "language=spa",
        "-metadata",
        "title=NexoLicitCR v0.9.0 - Brújula TI (escenario ficticio)",
        "-movflags",
        "+faststart",
        "-t",
        str(duration),
        str(output),
    ]
    with (work / "encode.log").open("w") as log:
        subprocess.run(command, check=True, stdout=log, stderr=log)  # noqa: S603
    summary = {
        "duration_seconds": round(duration, 3),
        "resolution": [1440, 900],
        "video_codec": "H.264",
        "audio_codec": "AAC",
        "subtitle_language": "es",
        "narration": "Voz sintética local Paulina, macOS",
        "scenario": "Brújula TI; base y documentos completamente ficticios",
        "capture": "Interacciones reales en navegador Playwright con perfil temporal vacío",
        "external_requests": "Bloqueadas durante la grabación; solo localhost:8010",
        "sicop_live_query": False,
        "size_bytes": output.stat().st_size,
    }
    (ROOT / "docs/entrega/demo/video.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Video listo: {duration:.1f} s; {output.stat().st_size / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
