import json
import re
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, TRANSLATE_MODEL

SYSTEM_PROMPT = """你是一名专业的日→中口译员。将每段日语翻译成口语化的简体中文。
要求：
- 译文自然流畅，适合朗读
- 保持原文的语气和情感
- 简洁，不要添加解释或补充

输入是一段 JSON 数组，每项包含 id 和 ja 字段。
严格按照输入顺序输出 JSON 数组，每项包含 id 和 zh 字段。只输出 JSON，不要其他内容。

示例：
输入：[{"id":0,"ja":"今日はいい天気ですね。"}]
输出：[{"id":0,"zh":"今天天气真好啊。"}]"""

MAX_SEGMENTS_PER_REQUEST = 30


def _build_user_message(segments: list[dict]) -> str:
    items = [{"id": i, "ja": seg["text"]} for i, seg in enumerate(segments)]
    return json.dumps(items, ensure_ascii=False)


def _parse_response(content: str, count: int) -> list[str]:
    # Try direct JSON parse
    try:
        data = json.loads(content)
        return _extract_translations(data, count)
    except json.JSONDecodeError:
        pass
    # Try to extract JSON array from markdown code fences or surrounding text
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return _extract_translations(data, count)
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Failed to parse translation response: {content[:200]}")


def _extract_translations(data: list[dict], count: int) -> list[str]:
    translations = [""] * count
    for item in data:
        idx = item["id"]
        if idx < count:
            translations[idx] = item["zh"]
    if any(t == "" for t in translations):
        raise ValueError(f"Missing translations for some segments: {translations}")
    return translations


def translate(segments: list[dict]) -> list[dict]:
    """Translate Japanese segments to Chinese via DeepSeek API. Returns segments with zh_text added."""
    if not segments:
        return segments

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    all_translations = []

    for chunk_start in range(0, len(segments), MAX_SEGMENTS_PER_REQUEST):
        chunk = segments[chunk_start:chunk_start + MAX_SEGMENTS_PER_REQUEST]
        response = client.chat.completions.create(
            model=TRANSLATE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(chunk)},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        translations = _parse_response(content, len(chunk))
        all_translations.extend(translations)

    result = []
    for seg, zh in zip(segments, all_translations):
        result.append({**seg, "zh_text": zh})
    return result
