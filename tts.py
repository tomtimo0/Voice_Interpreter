import os
import asyncio
import edge_tts
from config import TTS_VOICE, TTS_RATE


async def _synthesize_one(text: str, output_path: str):
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
    await communicate.save(output_path)


async def _synthesize_all(segments: list[dict], output_dir: str) -> list[dict]:
    tasks = []
    for i, seg in enumerate(segments):
        wav_path = os.path.join(output_dir, f"seg_{i:04d}.wav")
        tasks.append(_synthesize_one(seg["zh_text"], wav_path))
        seg["zh_wav_path"] = wav_path
    await asyncio.gather(*tasks)
    return segments


def synthesize(segments: list[dict], output_dir: str) -> list[dict]:
    """Generate Chinese TTS audio for each segment. Returns segments with zh_wav_path added."""
    os.makedirs(output_dir, exist_ok=True)
    return asyncio.run(_synthesize_all(segments, output_dir))
