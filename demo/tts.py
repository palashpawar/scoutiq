"""Render one ElevenLabs narration clip per scene in demo/narration.json.

    demo/.venv/bin/python demo/tts.py [--voice ID] [--only intro ask]   # key: ELEVENLABS_API_KEY in .env.local

Writes demo/out/audio/<scene>.mp3 and demo/out/durations.json.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
load_dotenv(ROOT.parent / ".env.local")  # ELEVENLABS_API_KEY, written by `elevenlabs onboard`
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George", premade narrator voice


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=os.getenv("ELEVENLABS_VOICE", DEFAULT_VOICE))
    ap.add_argument("--model", default="eleven_v4")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    if not os.getenv("ELEVENLABS_API_KEY"):
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

    scenes = json.loads((ROOT / "narration.json").read_text())
    audio_dir = OUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(scenes):
        if args.only is not None and s["id"] not in args.only:
            continue
        path = audio_dir / f"{s['id']}.mp3"
        audio = client.text_to_speech.convert(
            text=s["text"],
            voice_id=args.voice,
            model_id=args.model,
            output_format="mp3_44100_128",
            # neighbouring text keeps intonation continuous across separate clips
            previous_text=scenes[i - 1]["text"] if i else None,
            next_text=scenes[i + 1]["text"] if i + 1 < len(scenes) else None,
            voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
        )
        with path.open("wb") as fh:
            for chunk in audio:
                fh.write(chunk)
        print(f"{s['id']:10} {duration(path):5.1f}s")

    durations = {s["id"]: round(duration(audio_dir / f"{s['id']}.mp3"), 2) for s in scenes}
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"total narration {sum(durations.values()):.1f}s")


if __name__ == "__main__":
    main()
