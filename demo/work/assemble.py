"""Assemble the final MP4: title screens, scene clips, lower thirds, narration.

Per scene we build a VIDEO-ONLY intermediate (1280x720 30fps yuv420p h264):
1. cards: Ken Burns zoom off the PNG with fade in/out
2. clips: normalize the .webm, trim pre-paint blank, pad clone head/tail,
   overlay the lower-third (alpha fade), global fade in/out
The intermediates are concatenated (concat demuxer, -c:v copy), then a single
audio pass mixes every narration file at its exact scene offset over a
generative music bed, producing demo/EdFlow_Demo.mp4.
"""

import json
import subprocess
from pathlib import Path

from music_bed import render, write_wav

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

ROOT = Path(__file__).resolve().parent.parent  # demo/
WORK = ROOT / "work"
CLIPS = WORK / "clips"
AUDIO = WORK / "audio"
ASSETS = WORK / "assets"
SCENES = WORK / "scenes"
SCENES.mkdir(parents=True, exist_ok=True)

W, H = 1280, 720

HEAD = 1.0    # narration starts this long after a clip begins
TAIL = 1.7    # clip holds this long after narration ends
CARD_HEAD = 2.2
CARD_TAIL = 2.4
CARD_DIV = 3.4
TRIM_FRONT = 1.5

# film order; type card|clip|div
ORDER = [
    ("card", "open"),
    ("clip", "dashboard"),
    ("div", "div_learning"),
    ("clip", "students"),
    ("clip", "student_detail"),
    ("clip", "timetable"),
    ("clip", "attendance"),
    ("div", "div_finance"),
    ("clip", "fees"),
    ("clip", "finance"),
    ("clip", "payroll"),
    ("clip", "payroll_run"),
    ("div", "div_ops"),
    ("clip", "staff"),
    ("clip", "staff_detail"),
    ("clip", "parents"),
    ("clip", "hardware"),
    ("clip", "maintenance"),
    ("div", "div_platform"),
    ("clip", "communication"),
    ("clip", "notifications"),
    ("clip", "reports"),
    ("card", "close"),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG ERROR:", " ".join(cmd)[:400])
        print(r.stderr[-1800:])
        raise SystemExit(1)
    return r


def probe_duration(path):
    r = subprocess.run(
        [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def card_image(key):
    if key in ("open", "close"):
        return ASSETS / f"title_{key}.png"
    if key.startswith("div"):
        return ASSETS / f"{key}.png"
    return ASSETS / f"title_{key}.png"


def build_card(scene_key, out_path, duration):
    img = card_image(scene_key)
    fade_out = duration - 0.9
    vf = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+0.0010,1.16)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={int(duration*30)}:fps=30:s={W}x{H},"
        f"format=yuv420p,"
        f"fade=t=in:st=0:d=0.7,fade=t=out:st={fade_out:.2f}:d=0.9"
    )
    cmd = [
        FFMPEG, "-y", "-i", str(img),
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", "30",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    run(cmd)


def build_clip(key, out_path, nav_dur):
    head, tail = HEAD, TAIL
    dur = head + nav_dur + tail
    lt_in = head + 0.35
    lt_end = dur - 0.65
    lt_out = lt_end - 0.45
    fade_out_start = dur - 0.7

    clip = CLIPS / f"{key}.webm"
    lower_img = ASSETS / f"lower_{key}.png"

    vf_main = (
        f"[0:v]fps=30,trim=start={TRIM_FRONT},setpts=PTS-STARTPTS,"
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
        f"tpad=start_duration={head}:start_mode=clone:stop_duration={tail}:stop_mode=clone[vb];"
    )
    vf_lower = (
        f"[1:v]loop=loop=-1:size=1,"
        f"fade=t=in:st={lt_in:.2f}:d=0.45:alpha=1,"
        f"fade=t=out:st={lt_out:.2f}:d=0.45:alpha=1[lp];"
        f"[vb][lp]overlay=0:0:enable='between(t,{lt_in:.2f},{lt_end:.2f})',"
        f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_start:.2f}:d=0.7[vout];"
    )
    cmd = [
        FFMPEG, "-y",
        "-i", str(clip),
        "-loop", "1", "-i", str(lower_img),
        "-filter_complex", vf_main + vf_lower,
        "-map", "[vout]",
        "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", "30",
        str(out_path),
    ]
    run(cmd)


def main():
    manifest = json.loads((AUDIO / "manifest.json").read_text(encoding="utf-8"))
    con = WORK / "concat.txt"

    lines = []
    built = []  # (stype, key, duration)
    for stype, key in ORDER:
        out = SCENES / f"{len(lines):02d}_{key}.mp4"
        if stype == "clip":
            dur_total = HEAD + manifest[key]["duration"] + TAIL
            build_clip(key, out, manifest[key]["duration"])
        else:
            if key == "open":
                d = CARD_HEAD + manifest[key]["duration"] + CARD_TAIL
            elif key == "close":
                d = CARD_HEAD + manifest[key]["duration"] + CARD_TAIL
            else:
                d = CARD_DIV
            build_card(key, out, d)
        dur = probe_duration(out)
        built.append((stype, key, dur))
        lines.append(f"file '{out.as_posix()}'")
        print("built", out.name, f"{dur:7.2f}s")

    con.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- single audio pass over the concatenated video ----
    total = sum(b[2] for b in built)
    print("TOTAL VIDEO: %.2fs" % total)

    bed = AUDIO / "bed_film.wav"
    write_wav(bed, render(total + 2.0))

    # narration offsets: scene start + lead-in
    narr = []
    t = 0.0
    for stype, key, dur in built:
        if stype == "clip":
            narr.append((key, int((t + HEAD) * 1000), manifest[key]["duration"]))
        elif key in ("open", "close"):
            narr.append((key, int((t + CARD_HEAD) * 1000), manifest[key]["duration"]))
        t += dur
    print("narration cues:", [(k, o) for k, o, _ in narr])

    parts = [f"[1:a]aresample=48000,aformat=channel_layouts=stereo,"
             f"afade=t=in:st=0:d=2.5,"
             f"afade=t=out:st={total + 2.0 - 4.0:.2f}:d=4.0[bed]"]
    inputs = ["-f", "concat", "-safe", "0", "-i", str(con), "-i", str(bed)]
    mux = []
    for i, (key, off, _dur) in enumerate(narr, start=2):
        mp3 = AUDIO / f"{key}.mp3"
        if not mp3.exists():
            continue
        parts.append(
            f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"adelay={off}|{off},apad[na{i}]"
        )
        mux.append(f"[na{i}]")
        inputs += ["-i", str(mp3)]

    m = 1 + len(mux)  # bed + narrations
    graph = ";".join(parts) + ";" + \
        f"[bed]{''.join(mux)}amix=inputs={m}:duration=longest:normalize=0," \
        f"atrim=0:{total:.3f},asetpts=N/SR/TB,alimiter=limit=0.95[aout]"

    final = ROOT / "EdFlow_Demo.mp4"
    cmd = [
        FFMPEG, "-y", *inputs,
        "-filter_complex", graph,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(final),
    ]
    run(cmd)
    print("FINAL:", final, "dur=%.2f" % probe_duration(final),
          "size=%.1f MB" % (final.stat().st_size / 1e6))


if __name__ == "__main__":
    main()