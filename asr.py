import tempfile
import os
from pydub import AudioSegment
from openai import OpenAI
from config import LEMONFOX_API_KEY, LEMONFOX_BASE_URL, WHISPER_MODEL, ASR_LANGUAGE, ASR_CHUNK_SECONDS


def transcribe(audio_path: str) -> list[dict]:
    """Transcribe Japanese audio via Lemonfox Whisper API. Splits large files into chunks."""
    audio = AudioSegment.from_file(audio_path)
    duration_sec = len(audio) / 1000
    client = OpenAI(api_key=LEMONFOX_API_KEY, base_url=LEMONFOX_BASE_URL)

    if duration_sec <= ASR_CHUNK_SECONDS + 10:
        # Small enough for single request
        return _transcribe_chunk(client, audio_path, offset_sec=0)

    # Split into chunks with small overlap to avoid cutting words
    overlap = 2.0
    chunks = []
    cursor = 0.0
    while cursor < duration_sec:
        chunk_end = min(cursor + ASR_CHUNK_SECONDS + overlap, duration_sec)
        chunks.append((cursor, chunk_end))
        cursor += ASR_CHUNK_SECONDS

    print(f"  音频 {duration_sec:.0f}s，切分为 {len(chunks)} 段上传")
    all_segments = []
    for idx, (start, end) in enumerate(chunks):
        chunk_audio = audio[start * 1000:end * 1000]
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            chunk_path = tmp.name
        chunk_audio.export(chunk_path, format="wav")
        try:
            segs = _transcribe_chunk(client, chunk_path, offset_sec=start)
            all_segments.extend(segs)
            print(f"    段{idx+1}/{len(chunks)}: {len(segs)} 个片段")
        finally:
            os.unlink(chunk_path)

    # Deduplicate overlapping segments at boundaries
    merged = _merge_chunks(all_segments, overlap)
    print(f"  合并完成，共 {len(merged)} 段")
    return merged


def _transcribe_chunk(client: OpenAI, audio_path: str, offset_sec: float) -> list[dict]:
    """Transcribe a single audio chunk, adjusting timestamps by offset_sec."""
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=f,
            language=ASR_LANGUAGE,
            response_format="verbose_json",
        )
    segments = []
    for seg in result.segments:
        text = seg.text.strip()
        if text:
            segments.append({
                "text": text,
                "start": round(offset_sec + seg.start, 2),
                "end": round(offset_sec + seg.end, 2),
            })
    return segments


def _merge_chunks(all_segments: list[dict], overlap: float) -> list[dict]:
    """Merge segments from multiple chunks, removing duplicates at boundaries."""
    if len(all_segments) <= 1:
        return all_segments
    merged = [all_segments[0]]
    for cur in all_segments[1:]:
        prev = merged[-1]
        # Skip if current is entirely within previous (overlap duplicate)
        if cur["end"] <= prev["end"]:
            # Keep whichever has longer text (less truncated)
            if len(cur["text"]) > len(prev["text"]):
                merged[-1] = cur
            continue
        # Trim overlap: if current starts before previous ends
        if cur["start"] < prev["end"]:
            cur["start"] = round(prev["end"], 2)
        if cur["start"] < cur["end"]:
            merged.append(cur)
    return merged
