import os
import asyncio
import edge_tts
from pydub import AudioSegment
from config import TTS_VOICE, TTS_RATE, TTS_PROXY


async def _synthesize_one(text: str, output_path: str):
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, proxy=TTS_PROXY)
    await communicate.save(output_path)


async def _synthesize_all(segments: list[dict], output_dir: str) -> list[dict]:
    tasks = []
    for i, seg in enumerate(segments):
        wav_path = os.path.join(output_dir, f"seg_{i:04d}.wav")
        tasks.append(_synthesize_one(seg["zh_text"], wav_path))
        seg["zh_wav_path"] = wav_path
    await asyncio.gather(*tasks)
    for seg in segments:
        wav = AudioSegment.from_file(seg["zh_wav_path"])
        seg["zh_duration_ms"] = len(wav)
    return segments


def synthesize(segments: list[dict], output_dir: str) -> list[dict]:
    """Generate Chinese TTS via Edge TTS through local proxy. Returns segments enriched with zh_wav_path and zh_duration_ms."""
    os.makedirs(output_dir, exist_ok=True)
    return asyncio.run(_synthesize_all(segments, output_dir))
