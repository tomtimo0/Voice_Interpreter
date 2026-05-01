import argparse
import json
import os
import sys
from pathlib import Path

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


def _find_audio_files(paths: list[str], input_dir: str | None) -> list[str]:
    """Collect input files from CLI args and/or directory."""
    exts = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg",
            ".mp4", ".mov", ".mkv", ".avi", ".webm", ".wma", ".opus"}
    files = list(paths)
    if input_dir:
        d = Path(input_dir)
        if not d.is_dir():
            print(f"错误: 目录不存在 {input_dir}")
            sys.exit(1)
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                files.append(str(p))
    if not files:
        print("错误: 没有输入文件。用法: python main.py <文件1> [文件2 ...] 或 --input-dir <目录>")
        sys.exit(1)
    return files


def process_one(input_path: str, output_path: str, work_dir_base: str, args):
    """Run the full 4-stage pipeline on a single input file."""
    stem = Path(input_path).stem
    work_dir = os.path.join(work_dir_base, stem)
    os.makedirs(work_dir, exist_ok=True)
    tts_dir = os.path.join(work_dir, "tts_audio")

    asr_file = os.path.join(work_dir, "stage_1_asr.json")
    tr_file = os.path.join(work_dir, "stage_2_translate.json")
    tts_file = os.path.join(work_dir, "stage_3_tts.json")

    # Determine starting stage
    start_stage = args.from_stage
    if args.resume and start_stage is None:
        if os.path.exists(tts_file):
            start_stage = 4
        elif os.path.exists(tr_file):
            start_stage = 3
        elif os.path.exists(asr_file):
            start_stage = 2
        else:
            start_stage = 1
        names = {1: "ASR", 2: "翻译", 3: "TTS", 4: "混音"}
        print(f"  检测到已完成阶段 → 从阶段{start_stage}({names[start_stage]}) 继续")
    if start_stage is None:
        start_stage = 1

    segments = []

    # ---- 第 1 步：ASR ----
    if start_stage <= 1:
        print(f"  [1/4] ASR 识别中...")
        segments = transcribe(input_path)
        if not segments:
            print(f"  错误: 未识别到语音内容")
            return False
        print(f"  识别到 {len(segments)} 段语音")
        _save_json(segments, asr_file)
    else:
        segments = _load_json(asr_file)
        print(f"  [1/4] ASR 跳过 (缓存 {len(segments)} 段)")

    # ---- 第 2 步：翻译 ----
    if start_stage <= 2:
        print(f"  [2/4] 翻译中...")
        segments = translate(segments)
        _save_json(segments, tr_file)
        print(f"  {len(segments)} 段翻译完成")
    else:
        segments = _load_json(tr_file)
        print(f"  [2/4] 翻译跳过 (缓存 {len(segments)} 段)")

    # ---- 第 3 步：TTS ----
    if start_stage <= 3:
        print(f"  [3/4] TTS 合成中...")
        segments = synthesize(segments, tts_dir)
        _save_json(segments, tts_file)
        total_dur = sum(s.get("zh_duration_ms", 0) for s in segments) / 1000
        print(f"  {len(segments)} 段语音已合成 (总计 {total_dur:.1f}s)")
    else:
        segments = _load_json(tts_file)
        print(f"  [3/4] TTS 跳过 (缓存 {len(segments)} 段)")

    # ---- 第 4 步：混音 ----
    auto_tag = f", auto_vol" if args.auto_volume else ""
    print(f"  [4/4] 混合中 (delay={args.delay}s, duck={args.duck_ratio:.0%}, "
          f"zh_vol={args.chinese_volume:.0%}{auto_tag})...")
    mix(input_path, segments, output_path,
        delay=args.delay, duck_ratio=args.duck_ratio,
        chinese_volume=args.chinese_volume,
        auto_volume=args.auto_volume, vol_min=args.vol_min, vol_max=args.vol_max)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="AI 日语语音字幕 — 在日语音频上叠加中文同传语音")
    parser.add_argument("inputs", nargs="*",
                        help="输入音频文件 (可多个)")
    parser.add_argument("--input-dir",
                        help="批量处理目录下所有音频文件")
    parser.add_argument("-o", "--output-dir", default="output",
                        help="输出目录 (默认: output; 单文件时可为具体路径)")
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

    files = _find_audio_files(args.inputs, args.input_dir)

    # Determine output mode
    single_file = len(files) == 1 and not args.input_dir
    if single_file and not os.path.isdir(args.output_dir):
        outputs = [args.output_dir]
    else:
        os.makedirs(args.output_dir, exist_ok=True)
        outputs = [os.path.join(args.output_dir, Path(f).stem + "_output.wav") for f in files]

    total = len(files)
    for idx, (inp, out) in enumerate(zip(files, outputs)):
        print(f"\n{'#'*60}")
        print(f"[{idx+1}/{total}] {Path(inp).name}")
        print(f"  输出: {out}")
        print(f"{'#'*60}")
        try:
            ok = process_one(inp, out, args.work_dir, args)
            if ok:
                print(f"  ✓ 完成 → {out}")
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
