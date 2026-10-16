"""Voiceover + word-timed captions using edge-tts (free Microsoft neural voices)."""
import asyncio
import subprocess
from pathlib import Path

from . import config

MAX_WORDS_PER_CAPTION = 4


def _fmt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _to_srt(words: list[tuple[float, float, str]]) -> str:
    """Group (start, end, word) into short caption chunks."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= MAX_WORDS_PER_CAPTION or w[2].endswith((".", ",", "?", "!", ";", ":")):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    lines = []
    for i, c in enumerate(chunks, 1):
        start, end = c[0][0], c[-1][1]
        if i < len(chunks):
            end = max(end, chunks[i][0][0] - 0.02)  # hold until the next chunk starts
        text = " ".join(x[2] for x in c).upper()
        lines.append(f"{i}\n{_fmt(start)} --> {_fmt(end)}\n{text}\n")
    return "\n".join(lines)


async def _edge(text: str, mp3: Path) -> list[tuple[float, float, str]]:
    import edge_tts

    comm = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE,
                                boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
    return words


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _offline(text: str, mp3: Path) -> list[tuple[float, float, str]]:
    """Silent track with evenly timed words — for local tests without network."""
    tokens = text.split()
    per = 0.38
    total = max(1.0, len(tokens) * per)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", f"{total:.2f}", "-q:a", "6", str(mp3)],
                   check=True)
    return [(i * per, (i + 1) * per, t) for i, t in enumerate(tokens)]


def synth(text: str, mp3: Path, srt: Path, offline: bool = False) -> float:
    """Write mp3 + srt for `text`; returns audio duration in seconds."""
    mp3.parent.mkdir(parents=True, exist_ok=True)
    if offline:
        words = _offline(text, mp3)
    else:
        last = None
        for _ in range(3):
            try:
                words = asyncio.run(_edge(text, mp3))
                if words and mp3.stat().st_size > 1000:
                    break
                last = RuntimeError("edge-tts returned no audio")
            except Exception as exc:  # noqa: BLE001
                last = exc
        else:
            raise RuntimeError(f"TTS failed: {last}")
    srt.write_text(_to_srt(words), encoding="utf-8")
    return duration(mp3)
