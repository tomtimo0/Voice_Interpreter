from openai import OpenAI
from config import LEMONFOX_API_KEY, LEMONFOX_BASE_URL, WHISPER_MODEL, ASR_LANGUAGE


def transcribe(audio_path: str) -> list[dict]:
    """Transcribe Japanese audio via Lemonfox Whisper API, returning segments with timestamps."""
    client = OpenAI(api_key=LEMONFOX_API_KEY, base_url=LEMONFOX_BASE_URL)
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
            segments.append({"text": text, "start": seg.start, "end": seg.end})
    return segments
