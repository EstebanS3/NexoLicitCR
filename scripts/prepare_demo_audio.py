"""Build optional macOS narration and subtitles for the recorded demo.

Uses the local Spanish Paulina voice. Outputs private intermediate WAV files to
var/demo-video and publishable subtitles alongside the delivered video.
"""

import json
import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def timestamp(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def main():
    say = shutil.which("say")
    if not say:
        raise SystemExit("Esta herramienta opcional requiere la voz Paulina de macOS.")
    scenes = json.loads((ROOT / "docs/entrega/demo/narracion.json").read_text())
    out = ROOT / "var/demo-video/audio"
    out.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    subtitles = []
    samples = []
    params = None
    for index, scene in enumerate(scenes):
        source = out / f"{index:02}.txt"
        target = out / f"{index:02}.wav"
        source.write_text(scene["text"])
        subprocess.run(  # noqa: S603 -- local fixed executable and generated text file
            [
                say,
                "-v",
                "Paulina",
                "-r",
                "160",
                "-f",
                str(source),
                "-o",
                str(target),
                "--file-format=WAVE",
                "--data-format=LEI16@24000",
            ],
            check=True,
        )
        with wave.open(str(target), "rb") as audio:
            if audio.getnframes() == 0:
                raise SystemExit("La voz no produjo audio; comprobar permisos de macOS.")
            params = audio.getparams()
            duration = audio.getnframes() / audio.getframerate()
            frames = audio.readframes(audio.getnframes())
        # Leave an audible pause for the UI transition between narrated scenes.
        silence = b"\0" * (round(1.5 * params.framerate) * params.nchannels * params.sampwidth)
        samples.append(frames + silence)
        scene.update(start=round(cursor, 3), duration=round(duration + 1.5, 3))
        words = scene["text"].split()
        chunks = [words[i : i + 13] for i in range(0, len(words), 13)]
        total = len(words)
        offset = 0
        for chunk in chunks:
            begin = cursor + duration * offset / total
            offset += len(chunk)
            end = cursor + duration * offset / total
            subtitles.append(
                f"{len(subtitles) + 1}\n{timestamp(begin)} --> {timestamp(end)}\n"
                + " ".join(chunk)
                + "\n"
            )
        cursor += duration + 1.5
    with wave.open(str(out / "narracion.wav"), "wb") as combined:
        combined.setparams(params)
        combined.writeframes(b"".join(samples))
    (ROOT / "var/demo-video/timeline.json").write_text(
        json.dumps(scenes, ensure_ascii=False, indent=2) + "\n"
    )
    (ROOT / "docs/entrega/demo/NexoLicitCR_demo.srt").write_text("\n".join(subtitles))
    print(f"Narración generada: {cursor:.1f} segundos; {len(scenes)} escenas.")


if __name__ == "__main__":
    main()
