# LLM Voice Interpreter

日语音频 → 中文同传语音叠加工具。将日语讲话自动转写为带时间戳的文字、翻译为口语化中文、合成中文语音、叠加到原声上输出。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 需要 ffmpeg（pydub 格式转换依赖）

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env：LEMONFOX_API_KEY、DEEPSEEK_API_KEY

# 3. 运行
python main.py input.mp4 -o output.wav
```

## 使用方式

```bash
# 单个文件
python main.py input.mp4 -o output.wav

# 批量处理
python main.py file1.mp4 file2.mp3                # 输出到 output/ 目录
python main.py --input-dir ./videos                # 处理目录下所有音视频

# 断点续跑（每个文件独立 work/{文件名}/ 目录）
python main.py input.mp4 -w work --resume          # 自动检测断点继续
python main.py input.mp4 -w work --from-stage 3    # 从 TTS 阶段开始
```

### 完整参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `inputs` | — | 输入音频文件（可多个） |
| `--input-dir` | — | 批量处理目录 |
| `-o, --output-dir` | `output` | 输出目录；单文件时可指定具体路径 |
| `-w, --work-dir` | `work` | 中间文件缓存目录 |
| `--resume` | — | 自动检测已完成阶段并继续 |
| `--from-stage 1-4` | — | 从指定阶段开始 |
| `--delay` | `0.3` | 中文延迟起播（秒） |
| `--duck-ratio` | `1.0` | 原声压低比例（1.0=不压低，0.3=压到30%） |
| `--chinese-volume` | `0.1` | 中文语音基础音量（0-1） |
| `--auto-volume` | — | 根据原声段落响度自适应调整中文音量 |
| `--vol-min` | `0.5` | 自动音量下限倍数 |
| `--vol-max` | `1.5` | 自动音量上限倍数 |

## 架构

4 阶段管线，通过 segment dict 逐步传递和丰富数据：

```
音频 → asr.py → translate.py → tts.py → mixer.py → output.wav
```

| 阶段 | 模块 | 职责 | 技术 |
|------|------|------|------|
| 1. ASR | `asr.py` | 日语语音识别 + 时间戳 | Lemonfox Whisper API |
| 2. 翻译 | `translate.py` | 日→中口语化翻译 | DeepSeek v4-pro |
| 3. TTS | `tts.py` | 中文语音合成 | Edge TTS（免费） |
| 4. 混音 | `mixer.py` | 叠加、音量调整 | pydub |

### 断点续跑

每个阶段完成后自动保存结果到 `work/{文件名}/`：

```
work/input/
├── stage_1_asr.json       # 识别结果（239 段）
├── stage_2_translate.json # 翻译结果
├── stage_3_tts.json       # TTS 结果
└── tts_audio/             # 逐段 TTS 音频
    ├── seg_0000.wav
    └── ...
```

## 配置

API Key 通过 `.env` 文件设置：

```bash
LEMONFOX_API_KEY=xxx          # Lemonfox 语音识别
LEMONFOX_BASE_URL=https://api.lemonfox.ai/v1
DEEPSEEK_API_KEY=sk-xxx       # DeepSeek 翻译
DEEPSEEK_BASE_URL=https://api.deepseek.com
TTS_PROXY=http://127.0.0.1:10808  # Edge TTS 代理（选填）
```

其他参数在 `config.py` 中集中管理。

## 依赖

| 库 | 用途 |
|---|---|
| `openai` | Lemonfox ASR + DeepSeek 翻译 |
| `edge-tts` | 中文 TTS 合成 |
| `pydub` | 音频处理 |
| `python-dotenv` | 环境变量 |

> pydub 需要系统安装 ffmpeg。
