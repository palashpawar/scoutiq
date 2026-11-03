"""Combine the recorded walkthrough with the narration clips into demo/out/scoutiq-demo.mp4.

Each clip starts at its scene's mark; the video is scaled to 1080p with a title and an end card.
Also writes demo/out/captions.srt.

    python demo/compose.py
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
FONT = "/System/Library/Fonts/SFNS.ttf"
LEAD = 0.4  # start each clip just after the scene begins, so the action leads the voice


def text(t: str, size: int, y: str, start: float, end: float, color="white") -> str:
    return (f"drawtext=fontfile={FONT}:text='{t}':fontsize={size}:fontcolor={color}:x=(w-tw)/2:y={y}"
            f":enable='between(t,{start:.2f},{end:.2f})'")


def backdrop(start: float, end: float) -> str:
    """Navy scrim over the whole frame so card text reads cleanly over the app."""
    return f"drawbox=x=0:y=0:w=iw:h=ih:color=0x0a1628@0.92:t=fill:enable='between(t,{start:.2f},{end:.2f})'"


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    marks = json.loads((OUT / "marks.json").read_text())
    durations = json.loads((OUT / "durations.json").read_text())
    scenes = {s["id"]: s["text"] for s in json.loads((ROOT / "narration.json").read_text())}
    base = marks[0]["start"]
    total = marks[-1]["end"] - base
    at = {m["id"]: m["start"] - base + LEAD for m in marks}
    over = [(m["id"], round(at[m["id"]] + durations[m["id"]] - (m["end"] - base), 2)) for m in marks
            if at[m["id"]] + durations[m["id"]] > m["end"] - base + 0.05]
    if over:
        print("warning: narration runs past its scene:", over)

    outro = at["outro"]
    video = ",".join([
        f"trim=start={base:.2f}:duration={total:.2f},setpts=PTS-STARTPTS",
        "scale=1920:1080:flags=lanczos,fps=30",
        backdrop(0, 4.5),
        text("ScoutIQ", 96, "h*0.38", 0, 4.5, color="0x34d399"),
        text("AI soccer scouting assistant", 44, "h*0.38+130", 0, 4.5),
        text("Meta Global AI Developer Hackathon", 30, "h*0.38+200", 0, 4.5, color="0x94a3b8"),
        backdrop(outro + 7.0, total),
        text("ScoutIQ", 80, "h*0.33", outro + 7.0, total, color="0x34d399"),
        text("github.com/palashpawar/scoutiq", 48, "h*0.33+120", outro + 7.0, total),
        text("Muse Spark Open (Meta) on Modal  ·  StatsBomb Open Data  ·  Transfermarkt estimates", 30,
             "h*0.33+200", outro + 7.0, total, color="0x94a3b8"),
    ])
    ids = [m["id"] for m in marks]
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", str(OUT / "raw.webm")]
    for sid in ids:
        cmd += ["-i", str(OUT / "audio" / f"{sid}.mp3")]
    f = [f"[0:v]{video}[vout]"]
    for j, sid in enumerate(ids, start=1):
        f.append(f"[{j}:a]adelay={int(at[sid] * 1000)}:all=1[a{j}]")
    f.append("".join(f"[a{j}]" for j in range(1, len(ids) + 1))
             + f"amix=inputs={len(ids)}:normalize=0,loudnorm=I=-16:TP=-1.5,apad=whole_dur={total:.2f}[aout]")
    cmd += ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUT / "scoutiq-demo.mp4")]
    subprocess.run(cmd, check=True)

    srt, k = [], 1
    for sid in ids:
        sentences = [x for x in re.split(r"(?<=[.!?])\s+", scenes[sid]) if x]
        n, t = sum(len(x) for x in sentences), at[sid]
        for x in sentences:
            d = durations[sid] * len(x) / n
            srt.append(f"{k}\n{srt_time(t)} --> {srt_time(t + d)}\n{x}\n")
            t, k = t + d, k + 1
    (OUT / "captions.srt").write_text("\n".join(srt))
    print(f"total {total:.1f}s -> {OUT / 'scoutiq-demo.mp4'}")


if __name__ == "__main__":
    main()
