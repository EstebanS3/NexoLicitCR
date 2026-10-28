"""Edit a real browser recording: normal actions, accelerated waits, original music.

Optional macOS/FFmpeg production tooling, not an application dependency.
--prepare-audio creates local Spanish narration before record_sicop_demo.mjs.
With --ffmpeg PATH, assembles the final video from its private recording manifest.
"""

import argparse
import array
import json
import math
import re
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "var/demo-sicop-video"
DELIVERY = ROOT / "docs/entrega/demo-sicop"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
RATE = 24000


def run(command, log=None):
    # All paths are explicit local tools or generated media; never invoke a shell.
    return subprocess.run(command, check=True, stdout=log, stderr=log)  # noqa: S603


def prepare_audio():
    out = WORK / "audio"
    out.mkdir(parents=True, exist_ok=True)
    scenes = json.loads((DELIVERY / "narracion.json").read_text())
    for scene in scenes:
        if not scene["text"]:
            continue
        source, target = out / (scene["id"] + ".txt"), out / (scene["id"] + ".wav")
        source.write_text(scene["text"])
        run(
            [
                "/usr/bin/say",
                "-v",
                "Paulina",
                "-r",
                "170",
                "-f",
                str(source),
                "-o",
                str(target),
                "--file-format=WAVE",
                "--data-format=LEI16@24000",
            ]
        )
        with wave.open(str(target)) as audio:
            if not audio.getnframes():
                raise ValueError("La voz local no generó audio.")
            scene["audio_seconds"] = audio.getnframes() / audio.getframerate()
    (out / "durations.json").write_text(json.dumps(scenes, ensure_ascii=False, indent=2))
    print("Narración:", round(sum(x.get("audio_seconds", 0) for x in scenes), 1), "s")


def elevator_music():
    """Original mellow electric-piano cue, synthesized from notes without samples."""
    length = 12
    sound = [0.0] * (RATE * length)

    def tone(midi, at, duration, gain, bass=False):
        hz = 440 * 2 ** ((midi - 69) / 12)
        for i in range(min(round(duration * RATE), len(sound) - round(at * RATE))):
            t = i / RATE
            envelope = min(1, t / 0.018) * math.exp(-t * (1.5 if bass else 2.4))
            envelope *= min(1, (duration - t) / 0.12)
            phase = 2 * math.pi * hz * t
            sample = math.sin(phase) + 0.24 * math.sin(phase * 2) + 0.08 * math.sin(phase * 3)
            sound[round(at * RATE) + i] += gain * envelope * sample

    # Cmaj9 / Am9 / Dm9 / G13: a short original lounge progression at 100 BPM.
    chords = [
        (48, [60, 64, 67, 71, 74]),
        (45, [60, 64, 67, 71]),
        (50, [62, 65, 69, 72, 76]),
        (43, [59, 64, 65, 69]),
    ]
    for bar, (bass, chord) in enumerate(chords):
        for offset in [0, 1.2]:
            tone(bass, bar * 2.4 + offset, 1.15, 0.055, bass=True)
        for offset in [0.3, 1.5]:
            for note in chord:
                tone(note, bar * 2.4 + offset, 1.1, 0.014)
    melody = [
        (76, 0.6),
        (74, 1.05),
        (71, 1.8),
        (72, 3.0),
        (71, 3.6),
        (67, 4.05),
        (69, 5.4),
        (72, 6.0),
        (76, 6.45),
        (74, 7.8),
        (71, 8.4),
        (67, 9.0),
        (72, 9.6),
    ]
    for note, onset in melody:
        tone(note, onset, 0.7, 0.035)
    samples = array.array("h", [round(max(-0.9, min(0.9, sample)) * 32767) for sample in sound])
    target = WORK / "audio/musica_original.wav"
    with wave.open(str(target), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(samples.tobytes())
    return target


def stamp(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def duration(ffmpeg, source):
    result = subprocess.run(  # noqa: S603 -- explicit local executable and media file
        [ffmpeg, "-hide_banner", "-i", str(source)],
        capture_output=True,
        text=True,
    )
    found = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not found:
        raise ValueError("No se pudo medir la captura.")
    h, m, s = map(float, found.groups())
    return h * 3600 + m * 60 + s


def assemble(ffmpeg):
    recording = json.loads((WORK / "recording.json").read_text())
    if recording["failed"] or recording["errors"] or recording["responses"]:
        raise ValueError("La toma no terminó correctamente; revisarla o repetirla.")
    sources = {}
    for key, take in recording["takes"].items():
        source = Path(take["videoPath"]).resolve()
        if not source.is_relative_to(WORK / "raw"):
            raise ValueError("Captura fuera del directorio privado esperado.")
        lead = duration(ffmpeg, source) - take["end"]
        if not -1 <= lead <= 10:
            raise ValueError("Desfase inesperado en la captura; repetir la toma.")
        sources[key] = (source, max(0, lead))
    audio = {x["id"]: x for x in json.loads((WORK / "audio/durations.json").read_text())}
    music = elevator_music()
    segments, subtitles, cursor = [], [], 0.0
    clips = WORK / "clips"
    clips.mkdir(exist_ok=True)
    for index, event in enumerate(recording["events"]):
        source, lead = sources[event["take"]]
        scene = audio[event["id"]]
        real = event["end"] - event["start"]
        waiting = "espera" in event["id"]
        seconds = 8.0 if waiting and real > 8 else math.ceil(real * 25) / 25
        speed = real / seconds if waiting else 1
        title = clips / f"{index:02}.txt"
        title.write_text(f"{index + 1:02}  /  {scene['title']}")
        brand = clips / "brand.txt"
        brand.write_text("MESA NORTE CATERING · EMPRESA FICTICIA")
        origin = clips / "origin.txt"
        origin.write_text("NexoLicitCR · Consulta real de SICOP · 21 oct 2026")
        filters = [
            f"setpts=(PTS-STARTPTS)/{speed:.8f}",
            "fps=25",
            "pad=1600:1000:80:76:color=0x102b2a",
            f"drawtext=fontfile={FONT}:textfile='{brand}':x=100:y=17:fontsize=20:fontcolor=white",
            f"drawtext=fontfile={FONT}:textfile='{origin}':x=100:y=44:fontsize=14:fontcolor=0xacc9bf",
            f"drawtext=fontfile={FONT}:textfile='{title}':x=990:y=27:fontsize=20:fontcolor=white",
        ]
        if waiting:
            caption = clips / f"{index:02}-wait.txt"
            caption.write_text(
                f"ESPERA REAL ACELERADA  x{speed:.1f}\n{real:.0f} s grabados en 8 s · Un café mientras responde SICOP"
            )
            filters += [
                "drawbox=x=400:y=785:w=1040:h=100:color=0x102b2a@0.94:t=fill",
                f"drawtext=fontfile={FONT}:textfile='{caption}':x=430:y=807:fontsize=22:line_spacing=12:fontcolor=white",
            ]
            audio_path = music
            audio_filter = f"volume=2.8,afade=t=in:d=0.25,afade=t=out:st={seconds - 0.6}:d=0.6,apad"
        else:
            audio_path = WORK / "audio" / (event["id"] + ".wav")
            audio_filter = "adelay=150,apad"
            words = scene["text"].split()
            voice_duration = scene["audio_seconds"]
            for offset in range(0, len(words), 11):
                chunk = words[offset : offset + 11]
                begin = cursor + 0.15 + voice_duration * offset / len(words)
                end = cursor + 0.15 + voice_duration * (offset + len(chunk)) / len(words)
                subtitles.append(
                    f"{len(subtitles) + 1}\n{stamp(begin)} --> {stamp(end)}\n{' '.join(chunk)}\n"
                )
            if voice_duration + 0.15 > seconds + 0.1:
                raise ValueError(
                    f"La voz excede la escena {event['id']}; repetir con tiempos actualizados."
                )
        filters += ["tpad=stop_mode=clone:stop_duration=0.2", "format=yuv420p"]
        target = clips / f"{index:02}.mkv"
        command = [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-ss",
            str(lead + event["start"]),
            "-t",
            str(real),
            "-i",
            str(source),
            "-i",
            str(audio_path),
            "-vf",
            ",".join(filters),
            "-af",
            audio_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-threads",
            "4",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "24000",
            "-t",
            str(seconds),
            str(target),
        ]
        with (clips / f"{index:02}.log").open("w") as log:
            run(command, log)
        segments.append(
            {
                "id": event["id"],
                "title": scene["title"],
                "start": round(cursor, 3),
                "duration": seconds,
                "raw_duration": round(real, 3),
                "speed": round(speed, 3),
            }
        )
        cursor += seconds
        print(f"Editado {event['id']}: {seconds:.1f} s", flush=True)
    if not 180 <= cursor <= 300:
        raise ValueError(f"Duración fuera de 3–5 minutos: {cursor}")
    sub = DELIVERY / "NexoLicitCR_cliente_SICOP.srt"
    sub.write_text("\n".join(subtitles))
    concat = clips / "concat.txt"
    concat.write_text("\n".join(f"file '{i:02}.mkv'" for i in range(len(segments))))
    output = DELIVERY / "NexoLicitCR_cliente_SICOP.mp4"
    with (WORK / "encode.log").open("w") as log:
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-i",
                str(sub),
                "-map",
                "0:v",
                "-map",
                "0:a",
                "-map",
                "1:0",
                "-c:v",
                "copy",
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
                "title=NexoLicitCR - Mesa Norte Catering - SICOP real",
                "-movflags",
                "+faststart",
                str(output),
            ],
            log,
        )
    manifest = {
        "duration_seconds": round(cursor, 3),
        "resolution": [1600, 1000],
        "recorded_at": recording["recordedAt"],
        "sicop_live_query": True,
        "company": "Mesa Norte Catering (ficticia)",
        "source_procedure": "2026LD-000009-0033400001",
        "source_id": "20261002698:00",
        "narration": "Voz sintética local Paulina; interpretación de clienta ficticia",
        "music": "Composición original sintetizada localmente, sin muestras de terceros",
        "browser": "Chromium de Playwright con perfil temporal vacío",
        "edits": "Tramos de la misma cuenta y base; esperas aceleradas con rótulo. Acciones a velocidad normal. Pausa de producción entre consulta inicial y ampliación.",
        "production_cuts": recording["production_cuts"],
        "main_query": recording["mainJob"],
        "document_query": recording["docsJob"],
        "document_result": "Caso principal: PDF de 9 páginas listo. Otros concursos del lote: archivos no compatibles; consulta cancelada conservando resultados.",
        "segments": segments,
        "size_bytes": output.stat().st_size,
    }
    (DELIVERY / "video.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Video completo: {cursor:.2f} segundos; {output.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-audio", action="store_true")
    parser.add_argument("--ffmpeg")
    args = parser.parse_args()
    if args.prepare_audio:
        prepare_audio()
    elif args.ffmpeg and Path(args.ffmpeg).is_file():
        assemble(str(Path(args.ffmpeg).resolve()))
    else:
        parser.error("Usá --prepare-audio o --ffmpeg RUTA.")
