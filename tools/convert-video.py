#!/usr/bin/env python3
"""Convert arbitrary video files into MPEG program-stream .mpg files that
Rockbox's mpegplayer plugin can decode in real time on the iPod Video's
80MHz PP5021.

Format constraints below are verified against Rockbox/rockbox@master (the
wiki is stale/Anubis-blocked), not assumed:

- Container: MPEG program stream only (.mpg). apps/plugins/mpegplayer/
  mpeg_parser.c probes for a PES packet and sets STREAM_FMT_MPEG_PS; if none
  is found in the first 256KB it falls back to STREAM_FMT_MPV (raw video
  elementary stream, no audio). There is no MPEG-TS/MP4 support at all.
- Video: MPEG-1/MPEG-2 (apps/plugins/mpegplayer/libmpeg2/).
- Audio: MPEG audio layer I/II/III - audio_thread.c decodes via libmad.
- Resolution should be exactly 320x240 (the iPod Video LCD). mpegplayer can
  scale (stretch_image_plane) and crop (vo_set_clip_rect) video that doesn't
  match, but both cost CPU we don't have to spare - so this script encodes
  to the native size and lets ffmpeg do the (one-time, offline) scaling.
- Audio should be 44100Hz stereo - the hardware's native rate; anything else
  makes audio_thread.c reconfigure the DSP resampler at playback time.
- Framerate must be one of the MPEG-2-legal rates; mpeg2video hard-errors on
  anything else. This script snaps the source rate to the nearest legal one
  and caps at 30fps to keep the software decode inside the CPU budget.

Re-run per source file any time you want a different --bitrate/--fps/--fit.
"""
import argparse
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".flv",
    ".mpg", ".mpeg", ".ts",
}

# MPEG-2 legal frame rates (ffmpeg's mpeg2video encoder rejects anything
# else). Expressed as Fractions so both 30000/1001-style and integer rates
# compare exactly.
LEGAL_FPS = [
    Fraction(24000, 1001), Fraction(24), Fraction(25),
    Fraction(30000, 1001), Fraction(30),
    Fraction(50), Fraction(60000, 1001), Fraction(60),
]
# Rates we'll actually pick from automatically - capped at 30 so a 60fps
# source doesn't blow the CPU budget. --fps can still ask for 50/60 by hand.
AUTO_FPS = [f for f in LEGAL_FPS if f <= 30]

DEFAULT_MOUNT = "/Volumes/JUANCHO'S I"

FIT_FILTERS = {
    "pad": (
        "scale=320:240:force_original_aspect_ratio=decrease,"
        "pad=320:240:(ow-iw)/2:(oh-ih)/2,setsar=1"
    ),
    "crop": (
        "scale=320:240:force_original_aspect_ratio=increase,"
        "crop=320:240,setsar=1"
    ),
    "stretch": "scale=320:240,setsar=1",
}

# Safety margin (seconds) subtracted from the probed video duration when
# retrying a conversion whose source has a corrupted tail.
RETRY_TRIM_MARGIN = 15


def fmt_fps(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def nearest_legal_fps(src: Fraction, candidates) -> Fraction:
    return min(candidates, key=lambda f: abs(f - src))


def check_tools():
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        sys.exit(
            f"Missing required tool(s): {', '.join(missing)}. "
            "Install with `brew install ffmpeg`."
        )


def collect_inputs(paths, recursive):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            files.extend(sorted(f for f in it if f.suffix.lower() in VIDEO_EXTS))
        elif p.is_file():
            files.append(p)
        else:
            print(f"skip  {p}: not found", file=sys.stderr)
    return files


def probe(path: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_streams", "-show_format", str(path),
        ],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()}")
    data = json.loads(out.stdout)
    streams = data.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]
    if not vstreams:
        raise RuntimeError("no video stream found")
    v = vstreams[0]
    # avg_frame_rate (frames / duration) reflects true playback speed;
    # r_frame_rate is the container's nominal rate and can misreport it on
    # VFR sources (phone/screen recordings), which stretches the encoded
    # timeline against real-time audio - seen as video "dragging" and
    # desyncing more over the run. Prefer avg_frame_rate, falling back to
    # r_frame_rate only if avg is absent/zero.
    avg_str = v.get("avg_frame_rate")
    r_str = v.get("r_frame_rate")

    def parse_rate(s):
        if not s:
            return None
        num, den = s.split("/")
        den = int(den)
        return Fraction(int(num), den) if den else None

    src_fps = parse_rate(avg_str) or parse_rate(r_str) or Fraction(25)

    def stream_duration(s):
        d = s.get("duration") or data.get("format", {}).get("duration")
        return float(d) if d is not None else None

    return {
        "width": v.get("width"),
        "height": v.get("height"),
        "fps": src_fps,
        "has_audio": bool(astreams),
        "video_duration": stream_duration(v),
        "audio_duration": stream_duration(astreams[0]) if astreams else None,
    }


def build_cmd(src: Path, dst: Path, fps: Fraction, fit: str, vbitrate: str, abitrate: str, has_audio: bool, verbose: bool, trim_seconds=None):
    vf = FIT_FILTERS[fit]
    cmd = [
        "ffmpeg", "-y",
        "-loglevel", "info" if verbose else "error",
        "-stats",
        "-i", str(src),
        "-map", "0:v:0",
    ]
    if has_audio:
        cmd += ["-map", "0:a:0"]
    else:
        print(f"warn  {src.name}: no audio stream - output will be a silent "
              f"video-only .mpg (still plays fine, just no sound)", file=sys.stderr)
    cmd += [
        # Bound output to the shorter of video/audio, for sources (e.g. some
        # screen recordings) whose audio track legitimately runs longer than
        # the video track.
        "-shortest",
    ]
    if trim_seconds is not None:
        cmd += ["-t", str(trim_seconds)]
    cmd += [
        "-vf", vf,
        "-fps_mode", "cfr", "-r", fmt_fps(fps),
        "-c:v", "mpeg2video", "-b:v", vbitrate,
        # No -maxrate/-bufsize here: those (and -muxrate) tighten the MPEG-PS
        # muxer's internal STD buffer model beyond what it can actually
        # honor over a long encode, producing "buffer underflow" spam and
        # eventually a fatal ffmpeg exit 234 even on a clean source - letting
        # ffmpeg auto-choose its VBV/mux parameters avoids it.
        "-g", "15", "-aspect", "4:3",
    ]
    if has_audio:
        cmd += ["-c:a", "libmp3lame", "-b:a", abitrate, "-ar", "44100", "-ac", "2"]
    cmd += ["-f", "mpeg", str(dst)]
    return cmd


def run_ffmpeg(cmd, verbose: bool):
    """Run an ffmpeg command. Returns (ok, error_message)."""
    if verbose:
        # Stream ffmpeg's own progress/logging straight to the terminal
        # instead of capturing it, so -stats output updates live.
        result = subprocess.run(cmd)
        if result.returncode != 0:
            return False, f"ffmpeg exited {result.returncode}"
        return True, None
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip().splitlines()[-1] if result.stderr else "ffmpeg failed"
        return False, err
    return True, None


def find_ipod_video_dir(mount: str) -> Path:
    root = Path(mount)
    rb = root / ".rockbox"
    if not rb.is_dir():
        sys.exit(
            f"{rb} does not exist. Is the iPod mounted? "
            f"Pass its mount path to --ipod to override."
        )
    return root / "Video"


def main():
    ap = argparse.ArgumentParser(
        description="Convert videos to MPEG-PS .mpg files playable by Rockbox mpegplayer."
    )
    ap.add_argument("inputs", nargs="+", help="video file(s) or directory(ies)")
    ap.add_argument("-o", "--outdir", default="converted-video", help="output directory (default: ./converted-video)")
    ap.add_argument("--ipod", nargs="?", const=DEFAULT_MOUNT, metavar="MOUNT",
                     help=f"also copy outputs to <MOUNT>/Video/ (default mount: {DEFAULT_MOUNT})")
    ap.add_argument("--bitrate", default="600k", help="video bitrate (default: 600k)")
    ap.add_argument("--abitrate", default="128k", help="audio bitrate (default: 128k)")
    ap.add_argument("--fps", type=str, default=None,
                     help="force output framerate (must be MPEG-2 legal, e.g. 25, 30, 30000/1001)")
    ap.add_argument("--fit", choices=sorted(FIT_FILTERS), default="pad",
                     help="how to fit non-320x240 sources: pad (letterbox, default), crop, stretch")
    ap.add_argument("--recursive", action="store_true", help="recurse into input directories")
    ap.add_argument("-n", "--dry-run", action="store_true", help="print ffmpeg commands, run nothing")
    ap.add_argument("-f", "--force", action="store_true", help="overwrite existing outputs")
    ap.add_argument("-v", "--verbose", action="store_true",
                     help="show probe details, full ffmpeg command lines, and live ffmpeg output")
    args = ap.parse_args()

    check_tools()

    forced_fps = None
    if args.fps:
        num, _, den = args.fps.partition("/")
        forced_fps = Fraction(int(num), int(den) if den else 1)
        if forced_fps not in LEGAL_FPS:
            legal = ", ".join(fmt_fps(f) for f in LEGAL_FPS)
            sys.exit(f"--fps {args.fps} is not MPEG-2 legal. Choose one of: {legal}")

    files = collect_inputs(args.inputs, args.recursive)
    if not files:
        sys.exit("No input video files found.")

    outdir = Path(args.outdir)
    if not args.dry_run:
        outdir.mkdir(parents=True, exist_ok=True)

    ipod_video_dir = None
    if args.ipod and not args.dry_run:
        ipod_video_dir = find_ipod_video_dir(args.ipod)
        ipod_video_dir.mkdir(parents=True, exist_ok=True)

    failed = []
    for src in files:
        dst = outdir / (src.stem + ".mpg")
        if dst.exists() and not args.force and not args.dry_run:
            print(f"skip  {src.name}: {dst} already exists (use -f to overwrite)")
            continue
        try:
            info = probe(src)
            if args.verbose:
                print(f"probe {src.name}: {info['width']}x{info['height']} "
                      f"@{fmt_fps(info['fps'])}, audio={'yes' if info['has_audio'] else 'no'}")
            vdur, adur = info["video_duration"], info["audio_duration"]
            if vdur is not None and adur is not None and abs(vdur - adur) > 5:
                shorter = "video" if vdur < adur else "audio"
                print(f"warn  {src.name}: video track {vdur:.0f}s vs audio track {adur:.0f}s "
                      f"- output will be trimmed to the shorter ({shorter}) track", file=sys.stderr)
            fps = forced_fps or nearest_legal_fps(info["fps"], AUTO_FPS)
            cmd = build_cmd(src, dst, fps, args.fit, args.bitrate, args.abitrate, info["has_audio"], args.verbose)
            if args.dry_run:
                print(" ".join(cmd))
                continue
            ok, err = run_ffmpeg(cmd, args.verbose)
            if not ok and vdur is not None:
                # Some sources (e.g. screen recordings) have a genuinely
                # corrupted tail right around where the video track ends -
                # ffmpeg's demuxer desyncs on garbage bytes there (seen: an
                # "Invalid NAL unit size" a few seconds before the reported
                # video duration) and the whole encode dies instead of just
                # ending. Retry once with a hard cutoff safely before that
                # point rather than relying on natural stream end.
                trim = max(1, int(vdur) - RETRY_TRIM_MARGIN)
                print(f"warn  {src.name}: conversion failed ({err}) - retrying "
                      f"trimmed to {trim}s (source tail looks corrupted)", file=sys.stderr)
                cmd = build_cmd(src, dst, fps, args.fit, args.bitrate, args.abitrate,
                                 info["has_audio"], args.verbose, trim_seconds=trim)
                ok, err = run_ffmpeg(cmd, args.verbose)
            if not ok:
                raise RuntimeError(err)
            print(f"ok    {src.name} -> {dst} ({info['width']}x{info['height']}@{fmt_fps(info['fps'])} -> 320x240@{fmt_fps(fps)})")
            if ipod_video_dir is not None:
                shutil.copy2(dst, ipod_video_dir / dst.name)
                print(f"      copied to {ipod_video_dir / dst.name}")
        except Exception as e:
            print(f"FAIL  {src.name}: {e}", file=sys.stderr)
            failed.append(src)

    if failed:
        print(f"\n{len(failed)} of {len(files)} file(s) failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
