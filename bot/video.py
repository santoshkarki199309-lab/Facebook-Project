"""Render reels (9:16, 35–55 s) and long documentary videos (16:9, 3–7 min) from real
archive photographs and films, with voiceover and burned-in captions."""
import random
import subprocess
from pathlib import Path

from . import brand, config, media, tts

REEL = {"w": 1080, "h": 1920, "fps": 30,
        "captions": ("FontName=DejaVu Sans,FontSize=15,Bold=1,PrimaryColour=&H00FFFFFF,"
                     "OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=1,Outline=2,"
                     "Shadow=0,Alignment=2,MarginV=46")}
LONG = {"w": 1920, "h": 1080, "fps": 25,
        "captions": ("FontName=DejaVu Sans,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,"
                     "OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=1,Outline=2,"
                     "Shadow=0,Alignment=2,MarginV=16")}
AUDIO = ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:8])}...\n{res.stderr[-1500:]}")


def _subs(srt: Path, style: str) -> str:
    arg = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{arg}':force_style='{style}'"


def _audio_input(mp3: Path | None, dur: float) -> list[str]:
    if mp3:
        return ["-i", str(mp3)]
    return ["-f", "lavfi", "-t", f"{dur:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]


def image_clip(frame: Path, mp3: Path | None, srt: Path | None, dur: float, out: Path, fmt: dict,
               still: bool = False, overlay: Path | None = None) -> None:
    w, h, fps = fmt["w"], fmt["h"], fmt["fps"]
    frames = int(dur * fps) + fps // 2
    x = "iw/2-(iw/zoom/2)"
    motion = random.choice(["in", "out", "pan_r", "pan_l"])
    if still:
        z = "1.0"
    elif motion == "in":
        z = "min(zoom+0.0005,1.10)"
    elif motion == "out":
        z = "if(eq(on,0),1.10,max(zoom-0.0005,1.0))"
    else:
        z = "1.08"
        x = f"(iw-iw/zoom)*on/{frames}" if motion == "pan_r" else f"(iw-iw/zoom)*(1-on/{frames})"
    vf = (f"[0:v]scale={w * 2}:{h * 2},zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={w}x{h}:fps={fps}")
    ov_in = []
    if overlay:  # branding drawn after the camera move so it never gets cropped
        vf += "[z];[z][2:v]overlay=0:0"
        ov_in = ["-loop", "1", "-i", str(overlay)]
    if srt:
        vf += "," + _subs(srt, fmt["captions"])
    vf += ",format=yuv420p[v]"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(frame),
          *_audio_input(mp3, dur + 0.35), *ov_in, "-filter_complex", vf,
          "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
          "-r", str(fps), *AUDIO, "-t", f"{dur + 0.35:.2f}", str(out)])


def film_clip(v: media.Visual, overlay: Path, mp3: Path | None, srt: Path | None, dur: float,
              out: Path, fmt: dict, box: tuple[int, int]) -> None:
    """Archive film scene: blurred fill + film fitted inside `box` (top, height) + branding."""
    w, h, fps = fmt["w"], fmt["h"], fmt["fps"]
    top, fh = box
    start = media.random_start(v, dur)
    chain = (f"[0:v]fps={fps},setsar=1,split[a][b];"
             f"[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
             f"boxblur=20:2,eq=brightness=-0.22[bg];"
             f"[b]scale={w}:{fh}:force_original_aspect_ratio=decrease,setsar=1[fg];"
             f"[bg][fg]overlay=(W-w)/2:{top}+({fh}-h)/2[base];"
             f"[base][1:v]overlay=0:0")
    if srt:
        chain += "," + _subs(srt, fmt["captions"])
    chain += ",format=yuv420p[v]"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", str(start),
          "-i", str(v.path), "-loop", "1", "-i", str(overlay), *_audio_input(mp3, dur + 0.35),
          "-filter_complex", chain, "-map", "[v]", "-map", "2:a",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", str(fps),
          *AUDIO, "-t", f"{dur + 0.35:.2f}", str(out)])


def still_from_film(v: media.Visual, out: Path) -> Path:
    t = min(3.0, max(0.0, v.duration / 3)) if v.duration else 1.0
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(v.path),
          "-frames:v", "1", "-q:v", "2", str(out)])
    return out


def concat(clips: list[Path], out: Path) -> Path:
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", "-movflags", "+faststart", str(out)])
    return out


def add_music(video: Path, out: Path, volume: float = 0.12) -> Path:
    tracks = sorted(config.MUSIC_DIR.glob("*.mp3")) if config.MUSIC_DIR.exists() else []
    if not tracks:
        return video
    track = random.choice(tracks)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-stream_loop", "-1",
          "-i", str(track), "-filter_complex",
          f"[1:a]volume={volume}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
          "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AUDIO, "-movflags", "+faststart",
          str(out)])
    return out


# ------------------------------------------------------------------ reels

def render_reel(post: dict, workdir: Path, offline: bool = False) -> tuple[Path, list[str]]:
    workdir.mkdir(parents=True, exist_ok=True)
    scenes = post["scenes"]
    visuals = media.resolve_many(scenes, workdir, "s", offline)
    box = (int(REEL["h"] * brand.REEL_IMG_TOP), int(REEL["h"] * brand.REEL_IMG_H))
    clips = []
    for i, (scene, v) in enumerate(zip(scenes, visuals)):
        hook = (post.get("hook_text") or post.get("title")) if i == 0 else None
        mp3, srt = workdir / f"s{i}.mp3", workdir / f"s{i}.srt"
        dur = tts.synth(scene["narration"], mp3, srt, offline=offline)
        clip = workdir / f"s{i}.mp4"
        if v.kind == "video":
            ov = brand.reel_overlay(workdir / f"s{i}_ov.png", hook=hook, tagline=v.tag,
                                    label=scene.get("label"))
            film_clip(v, ov, mp3, srt, dur, clip, REEL, box)
        else:
            frame = brand.reel_frame(v.path, workdir / f"s{i}_frame.jpg", hook=hook,
                                     tagline=v.tag, label=scene.get("label"))
            image_clip(frame, mp3, srt, dur, clip, REEL, still=bool(hook))
        clips.append(clip)
        print(f"[reel] scene {i + 1}/{len(scenes)} {v.kind} {dur:.1f}s")
    final = add_music(concat(clips, workdir / "joined.mp4"), workdir / "reel_music.mp4")
    total = tts.duration(final)
    print(f"[reel] final {final.name} {total:.1f}s")
    if not 3 <= total <= 90:
        raise RuntimeError(f"Reel length {total:.1f}s is outside Facebook's 3–90s limit")
    return final, media.credits_of(visuals)


# ------------------------------------------------------------------ long documentary video

def render_long(post: dict, workdir: Path, offline: bool = False) -> tuple[Path, list[str]]:
    workdir.mkdir(parents=True, exist_ok=True)
    flat = [(ci, sc) for ci, ch in enumerate(post["chapters"]) for sc in ch["scenes"]]
    visuals = media.resolve_many([sc for _, sc in flat], workdir, "v", offline)
    clips, last_ch = [], -1
    for i, ((ci, scene), v) in enumerate(zip(flat, visuals)):
        if ci != last_ch:  # chapter card: 3 s title over the chapter's first archive picture
            last_ch = ci
            chapter = post["chapters"][ci]
            title = post["title"] if ci == 0 else chapter["title"]
            label = None if ci == 0 else f"Part {ci + 1}"
            pic = v.path if v.kind == "image" else still_from_film(v, workdir / f"v{i}_still.jpg")
            card = brand.land_frame(pic, workdir / f"c{ci}_card.jpg", tagline=v.tag, label=label,
                                    title=title)
            cclip = workdir / f"c{ci}.mp4"
            image_clip(card, None, None, 3.2 if ci == 0 else 2.6, cclip, LONG, still=True)
            clips.append(cclip)
        mp3, srt = workdir / f"v{i}.mp3", workdir / f"v{i}.srt"
        dur = tts.synth(scene["narration"], mp3, srt, offline=offline)
        clip = workdir / f"v{i}.mp4"
        if v.kind == "video":
            ov = brand.land_overlay(workdir / f"v{i}_ov.png", tagline=v.tag, label=scene.get("label"))
            film_clip(v, ov, mp3, srt, dur, clip, LONG, (0, LONG["h"]))
        else:
            frame = brand.land_frame(v.path, workdir / f"v{i}_frame.jpg", text=False)
            ov = brand.land_overlay(workdir / f"v{i}_ov.png", tagline=v.tag, label=scene.get("label"))
            image_clip(frame, mp3, srt, dur, clip, LONG, overlay=ov)
        clips.append(clip)
        print(f"[long] scene {i + 1}/{len(flat)} {v.kind} {dur:.1f}s")
    final = add_music(concat(clips, workdir / "long.mp4"), workdir / "long_music.mp4", 0.08)
    total = tts.duration(final)
    print(f"[long] final {final.name} {total / 60:.1f} min")
    if not 120 <= total <= 1200:
        raise RuntimeError(f"Long video is {total:.0f}s; expected 2–20 minutes")
    return final, media.credits_of(visuals)
