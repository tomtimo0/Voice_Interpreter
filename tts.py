import os
import asyncio
import edge_tts
from pydub import AudioSegment
from config import TTS_VOICE, TTS_RATE, TTS_PROXY, TTS_MAX_CONCURRENT


async def _synthesize_one(text: str, output_path: str) -> None:
    """Synthesize a single segment to WAV via Edge TTS."""
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, proxy=TTS_PROXY)
    await communicate.save(output_path)


async def _synthesize_bounded(
    semaphore: asyncio.Semaphore, text: str, output_path: str
) -> None:
    """Run `_synthesize_one` under a semaphore to cap concurrent WebSocket sessions."""
    async with semaphore:
        await _synthesize_one(text, output_path)


async def _synthesize_all(segments: list[dict], output_dir: str) -> list[dict]:
    """Generate WAV per segment with at most ``TTS_MAX_CONCURRENT`` Edge calls at once."""
    semaphore = asyncio.Semaphore(TTS_MAX_CONCURRENT)
    tasks = []
    for i, seg in enumerate(segments):
        wav_path = os.path.join(output_dir, f"seg_{i:04d}.wav")
        tasks.append(_synthesize_bounded(semaphore, seg["zh_text"], wav_path))
        seg["zh_wav_path"] = wav_path
    await asyncio.gather(*tasks)
    for seg in segments:
        wav = AudioSegment.from_file(seg["zh_wav_path"])
        seg["zh_duration_ms"] = len(wav)
    return segments


def synthesize(segments: list[dict], output_dir: str) -> list[dict]:
    """
    Generate Chinese TTS via Edge TTS (optionally via proxy).

    Concurrency is capped by ``config.TTS_MAX_CONCURRENT`` to reduce timeouts through proxies.

    @returns Segments with ``zh_wav_path`` and ``zh_duration_ms``.
    """
    os.makedirs(output_dir, exist_ok=True)
    return asyncio.run(_synthesize_all(segments, output_dir))
