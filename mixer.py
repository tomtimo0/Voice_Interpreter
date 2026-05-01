import math
from pydub import AudioSegment
from config import DEFAULT_DELAY, DEFAULT_DUCK_RATIO, DEFAULT_CHINESE_VOLUME
from config import FADE_IN_MS, FADE_OUT_MS, DUCK_FADE_MS


def _gain_db_from_ratio(ratio: float) -> float:
    """Convert a linear volume ratio to dB gain (negative for reduction)."""
    return 20 * math.log10(max(ratio, 0.01))


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping intervals. Each interval is (start_ms, end_ms)."""
    if not intervals:
        return []
    sorted_intervals = sorted(intervals)
    merged = [list(sorted_intervals[0])]
    for start, end in sorted_intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def _build_ducked(original: AudioSegment, duck_regions: list[tuple[int, int]],
                  duck_gain_db: float) -> AudioSegment:
    """Build a version of original with volume ducked in the specified regions."""
    pieces = []
    last_end = 0
    total = len(original)

    for start, end in duck_regions:
        start = max(0, start)
        end = min(total, end)
        # Normal section before the duck region
        if start > last_end:
            pieces.append(original[last_end:start])
        # Duck section with fades
        ducked = original[start:end].apply_gain(duck_gain_db)
        if ducked.duration_seconds * 1000 > DUCK_FADE_MS * 2:
            ducked = ducked.fade_in(DUCK_FADE_MS).fade_out(DUCK_FADE_MS)
        pieces.append(ducked)
        last_end = end

    # Tail after last duck region
    if last_end < total:
        pieces.append(original[last_end:])

    if not pieces:
        return original

    result = pieces[0]
    for p in pieces[1:]:
        result += p
    return result


def mix(audio_path: str, segments: list[dict], output_path: str,
        delay: float = DEFAULT_DELAY, duck_ratio: float = DEFAULT_DUCK_RATIO,
        chinese_volume: float = DEFAULT_CHINESE_VOLUME):
    """Mix original audio with Chinese TTS overlay using ducking."""
    original = AudioSegment.from_file(audio_path)
    total_ms = len(original)

    # Compute duck regions based on Chinese TTS playback
    duck_intervals = []
    for seg in segments:
        if "zh_wav_path" not in seg:
            continue
        zh_start_ms = int((seg["start"] + delay) * 1000)
        zh_wav = AudioSegment.from_file(seg["zh_wav_path"])
        zh_duration_ms = len(zh_wav)
        zh_end_ms = zh_start_ms + zh_duration_ms
        seg["zh_duration_ms"] = zh_duration_ms

        duck_start = max(0, zh_start_ms - DUCK_FADE_MS)
        duck_end = min(total_ms, zh_end_ms + DUCK_FADE_MS)
        duck_intervals.append((duck_start, duck_end))

    merged = _merge_intervals(duck_intervals)
    duck_gain_db = _gain_db_from_ratio(duck_ratio)
    chinese_gain_db = _gain_db_from_ratio(chinese_volume)

    ducked = _build_ducked(original, merged, duck_gain_db)

    # Overlay Chinese TTS
    final = ducked
    for seg in segments:
        if "zh_wav_path" not in seg:
            continue
        tts = AudioSegment.from_file(seg["zh_wav_path"])
        tts = tts.apply_gain(chinese_gain_db)
        tts = tts.fade_in(FADE_IN_MS).fade_out(FADE_OUT_MS)
        pos_ms = int((seg["start"] + delay) * 1000)
        final = final.overlay(tts, position=pos_ms)

    final = final.set_frame_rate(44100).set_sample_width(2).set_channels(2)
    final.export(output_path, format="wav")
