"""Render a 1080x1920 reel: one AI image per scene, slow zoom, voiceover, burned-in captions."""
import random
import subprocess
from pathlib import Path

from . import brand, config, media, tts

FPS = 30
CAPTION_STYLE = (
    "FontName=DejaVu Sans,FontSize=15,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=46"
)


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:6])}...\n{res.stderr[-1500:]}")


def _scene_clip(frame: Path, mp3: Path, srt: Path, dur: float, out: Path,
                still: bool = False) -> None:
    frames = int(dur * FPS) + FPS // 2
    x = "iw/2-(iw/zoom/2)"
    motion = random.choice(["in", "out", "pan_r", "pan_l"])
    if still:  # hook scene: keep the headline fully on screen
        z = "1.0"
    elif motion == "in":
        z = "min(zoom+0.0005,1.10)"
    elif motion == "out":
        z = "if(eq(on,0),1.10,max(zoom-0.0005,1.0))"
    else:  # slow horizontal pan across the picture
        z = "1.08"
        x = f"(iw-iw/zoom)*on/{frames}" if motion == "pan_r" else f"(iw-iw/zoom)*(1-on/{frames})"
    srt_arg = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    vf = (
        f"scale=2160:3840,zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps={FPS},"
        f"subtitles='{srt_arg}':force_style='{CAPTION_STYLE}',format=yuv420p"
    )
    _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(frame), "-i", str(mp3),
          "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
          "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
          "-t", f"{dur + 0.35:.2f}", str(out)])


def _add_music(video: Path, out: Path) -> Path:
    tracks = sorted(config.MUSIC_DIR.glob("*.mp3")) if config.MUSIC_DIR.exists() else []
    if not tracks:
        return video
    track = random.choice(tracks)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-stream_loop", "-1",
          "-i", str(track), "-filter_complex",
          "[1:a]volume=0.12[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
          "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
          str(out)])
    return out


def render(post: dict, workdir: Path, offline: bool = False) -> tuple[Path, list[str]]:
    """Build the reel for a queue item of type 'reel'. Returns (mp4 path, image credits)."""
    workdir.mkdir(parents=True, exist_ok=True)
    clips, credits = [], []
    for i, scene in enumerate(post["scenes"]):
        raw, tag, credit = media.picture(scene, workdir / f"s{i}_raw.jpg", offline=offline)
        if credit and credit not in credits:
            credits.append(credit)
        hook = (post.get("hook_text") or post.get("title")) if i == 0 else None
        frame = brand.reel_frame(raw, workdir / f"s{i}_frame.jpg", hook=hook, tagline=tag,
                                 label=scene.get("label"))
        mp3, srt = workdir / f"s{i}.mp3", workdir / f"s{i}.srt"
        dur = tts.synth(scene["narration"], mp3, srt, offline=offline)
        clip = workdir / f"s{i}.mp4"
        _scene_clip(frame, mp3, srt, dur, clip, still=bool(hook))
        clips.append(clip)
        print(f"[reel] scene {i + 1}/{len(post['scenes'])} {dur:.1f}s")

    listing = workdir / "clips.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips))
    joined = workdir / "joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
          str(listing), "-c", "copy", "-movflags", "+faststart", str(joined)])
    final = _add_music(joined, workdir / "reel_music.mp4")
    total = tts.duration(final)
    print(f"[reel] final {final.name} {total:.1f}s")
    if not 3 <= total <= 90:
        raise RuntimeError(f"Reel length {total:.1f}s is outside Facebook's 3–90s limit")
    return final, credits
