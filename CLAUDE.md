# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

日语语音同传叠加工具。输入日语音频，输出叠加了中文同传语音的混音文件——原声保留但音量自动压低（ducking），中文 TTS 叠在上方。

## 运行方式

```bash
# 安装依赖
python -m pip install -r requirements.txt

# 需要 ffmpeg（pydub 格式转换依赖）

# 配置 API Key（Lemonfox + DeepSeek）
cp .env.example .env
# 编辑 .env：LEMONFOX_API_KEY、DEEPSEEK_API_KEY

# 运行
python main.py input.mp4 -o output.wav
python main.py input.mp3 -o output.wav --delay 0.5 --duck-ratio 0.25

# 断点续跑
python main.py input.mp3 -w work                 # 保存中间文件到 work/
python main.py input.mp3 -w work --resume        # 自动检测断点继续
python main.py input.mp3 -w work --from-stage 3  # 从 TTS 阶段开始
```

## 架构

4 阶段管线，通过段列表（segment dicts）传递数据：

```
main.py  →  asr.py  →  translate.py  →  tts.py  →  mixer.py
```

**Segment dict schema** 在管线中逐步丰富：

```python
# asr 产出
{"text": str, "start": float, "end": float}
# translate 添加
{"text": str, "start": float, "end": float, "zh_text": str}
# tts 添加
{..., "zh_wav_path": str, "zh_duration_ms": int}  # mixer 内部
```

### 断点续跑机制

每个阶段完成后将结果写入 `-w` 指定的工作目录：
- `stage_1_asr.json` — 识别结果
- `stage_2_translate.json` — 翻译结果
- `stage_3_tts.json` — TTS 结果（含 wav 文件路径）

`--resume` 自动检测最新完成的阶段并继续；`--from-stage N` 手动指定起点。

## 各模块

### asr.py — `transcribe(audio_path) -> list[dict]`
Lemonfox Whisper API（OpenAI 兼容，`base_url=https://api.lemonfox.ai/v1`，`whisper-1`，`language="ja"`，`verbose_json`），返回段级时间戳。过滤空段。

### translate.py — `translate(segments) -> list[dict]`
DeepSeek API（`deepseek-v4-pro`，OpenAI 兼容 SDK），批量日→中翻译。System prompt 要求输出口语化口译风格，结构化 JSON（`[{id, ja}] → [{id, zh}]`）。每批最多 30 段。`_parse_response` 自动处理裸 JSON 或 markdown 代码块包裹的响应。

### tts.py — `synthesize(segments, output_dir) -> list[dict]`
Edge TTS（免费），中文语音 `zh-CN-XiaoxiaoNeural`，语速 +10%。通过本地 HTTP 代理（`TTS_PROXY` 配置项）访问 Bing Speech 服务。所有 segment 通过 `asyncio.gather` 并发合成。合成后写入 `zh_wav_path` 和 `zh_duration_ms`。

### mixer.py — `mix(audio_path, segments, output_path, delay, duck_ratio, chinese_volume)`
pydub 音频处理。核心逻辑：
1. 根据中文 TTS 的播放位置 + DUCK_FADE_MS padding 计算 duck 区间
2. 合并重叠区间（`_merge_intervals`）
3. 将原声按 duck 区间切片，压低音量段施加 `apply_gain` + `fade_in/fade_out`
4. 将切片段拼接回完整音频（`+` 运算符）
5. 逐段 `overlay` 中文 TTS 到拼接后的音频上
6. 输出 44.1kHz / 16bit / 立体声 WAV

### config.py
所有可调参数集中管理。`.env` 提供 API Key。混音参数（FADE_IN_MS、DUCK_FADE_MS 等）目前是常量，可考虑改为 CLI 参数。

## 依赖

| 库 | 用途 |
|---|---|
| `openai` | Lemonfox ASR + DeepSeek 翻译（兼容 SDK） |
| `edge-tts` | 中文语音合成 |
| `pydub` | 音频裁剪、增益、叠加 |
| `python-dotenv` | 环境变量加载 |

pydub 需要系统安装 ffmpeg 处理非 WAV 格式。
