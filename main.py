import argparse
import json
import os
import sys

from asr import transcribe
from translate import translate
from tts import synthesize
from mixer import mix
from config import DEFAULT_DELAY, DEFAULT_DUCK_RATIO, DEFAULT_CHINESE_VOLUME
from config import TRANSLATE_MODEL, TTS_VOICE


def _load_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(data: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="AI 日语语音字幕 — 在日语音频上叠加中文同传语音")
    parser.add_argument("input", help="输入音频文件路径 (mp3/wav/m4a 等)")
    parser.add_argument("-o", "--output", default="output.wav",
                        help="输出文件路径 (默认: output.wav)")
    parser.add_argument("-w", "--work-dir", default="work",
                        help="中间文件目录 (默认: work)")
    parser.add_argument("--resume", action="store_true",
                        help="自动检测已完成阶段并继续")
    parser.add_argument("--from-stage", type=int, choices=[1, 2, 3, 4],
                        help="从指定阶段开始 (1=ASR, 2=翻译, 3=TTS, 4=混音)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"中文语音延迟偏移 (秒, 默认: {DEFAULT_DELAY})")
    parser.add_argument("--duck-ratio", type=float, default=DEFAULT_DUCK_RATIO,
                        help=f"中文播放时原声音量比例 (0-1, 默认: {DEFAULT_DUCK_RATIO})")
    parser.add_argument("--chinese-volume", type=float, default=DEFAULT_CHINESE_VOLUME,
                        help=f"中文语音音量 (0-1, 默认: {DEFAULT_CHINESE_VOLUME})")
    parser.add_argument("--auto-volume", action="store_true",
                        help="根据原声每段响度自动调整中文音量")
    parser.add_argument("--vol-min", type=float, default=0.5,
                        help="自动音量下限倍数 (默认: 0.5)")
    parser.add_argument("--vol-max", type=float, default=1.5,
                        help="自动音量上限倍数 (默认: 1.5)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 找不到输入文件 {args.input}")
        sys.exit(1)

    work_dir = args.work_dir
    os.makedirs(work_dir, exist_ok=True)
    tts_dir = work_dir  # TTS .wav files live alongside JSON

    # File paths for each stage
    asr_file = os.path.join(work_dir, "stage_1_asr.json")
    tr_file = os.path.join(work_dir, "stage_2_translate.json")
    tts_file = os.path.join(work_dir, "stage_3_tts.json")

    # Determine starting stage
    start_stage = args.from_stage
    if args.resume and start_stage is None:
        # Auto-detect: find the latest completed stage
        if os.path.exists(tts_file):
            start_stage = 4
        elif os.path.exists(tr_file):
            start_stage = 3
        elif os.path.exists(asr_file):
            start_stage = 2
        else:
            start_stage = 1
        stage_names = {1: "ASR", 2: "翻译", 3: "TTS", 4: "混音"}
        print(f"检测到已完成的阶段，从 阶段{start_stage}({stage_names[start_stage]}) 继续")
    if start_stage is None:
        start_stage = 1

    segments = []

    # ---- 第 1 步：ASR ----
    if start_stage <= 1:
        print(f"\n{'='*60}")
        print(f"[1/4] 语音识别 (Lemonfox Whisper)")
        print(f"{'='*60}")
        segments = transcribe(args.input)
        if not segments:
            print("错误: 未识别到语音内容")
            sys.exit(1)
        print(f"共识别 {len(segments)} 段语音:\n")
        for i, seg in enumerate(segments):
            print(f"  #{i+1}  [{seg['start']:6.1f}s → {seg['end']:6.1f}s]  "
                  f"{(seg['end']-seg['start']):.1f}s")
            print(f"      {seg['text']}\n")
        _save_json(segments, asr_file)
        print(f"  [已保存] {asr_file}")
    else:
        print(f"\n[1/4] 跳过 ASR (加载缓存)")
        segments = _load_json(asr_file)
        print(f"  已加载 {len(segments)} 段")

    # ---- 第 2 步：翻译 ----
    if start_stage <= 2:
        print(f"\n{'='*60}")
        print(f"[2/4] 日→中翻译 (DeepSeek {TRANSLATE_MODEL})")
        print(f"{'='*60}")
        segments = translate(segments)
        for i, seg in enumerate(segments):
            print(f"  #{i+1}  [{seg['start']:.1f}s - {seg['end']:.1f}s]")
            print(f"      JA: {seg['text']}")
            print(f"      ZH: {seg['zh_text']}")
            print()
        _save_json(segments, tr_file)
        print(f"  [已保存] {tr_file}")
    else:
        print(f"\n[2/4] 跳过翻译 (加载缓存)")
        segments = _load_json(tr_file)
        print(f"  已加载 {len(segments)} 段")

    # ---- 第 3 步：TTS ----
    if start_stage <= 3:
        print(f"\n{'='*60}")
        print(f"[3/4] 中文语音合成 (Edge TTS, {TTS_VOICE})")
        print(f"{'='*60}")
        segments = synthesize(segments, tts_dir)
        for i, seg in enumerate(segments):
            dur = seg.get("zh_duration_ms", 0) / 1000
            print(f"  #{i+1}  已合成  "
                  f"时长={dur:.1f}s  文件={os.path.basename(seg['zh_wav_path'])}")
        print()
        _save_json(segments, tts_file)
        print(f"  [已保存] {tts_file}")
    else:
        print(f"\n[3/4] 跳过 TTS (加载缓存)")
        segments = _load_json(tts_file)
        print(f"  已加载 {len(segments)} 段 (含 TTS 音频)")

    # ---- 第 4 步：混音 ----
    auto_tag = f", auto_vol=[{args.vol_min}x~{args.vol_max}x]" if args.auto_volume else ""
    print(f"\n{'='*60}")
    print(f"[4/4] 音频混合 (delay={args.delay}s, duck={args.duck_ratio:.0%}, "
          f"zh_vol={args.chinese_volume:.0%}{auto_tag})")
    print(f"{'='*60}")
    mix(args.input, segments, args.output,
        delay=args.delay, duck_ratio=args.duck_ratio,
        chinese_volume=args.chinese_volume,
        auto_volume=args.auto_volume, vol_min=args.vol_min, vol_max=args.vol_max)
    print(f"\n✓ 输出文件: {args.output}")


if __name__ == "__main__":
    main()
