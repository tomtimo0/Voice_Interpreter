import argparse
import os
import shutil
import tempfile
import sys

from asr import transcribe
from translate import translate
from tts import synthesize
from mixer import mix
from config import DEFAULT_DELAY, DEFAULT_DUCK_RATIO, DEFAULT_CHINESE_VOLUME


def main():
    parser = argparse.ArgumentParser(
        description="AI 日语语音字幕 — 在日语音频上叠加中文同传语音")
    parser.add_argument("input", help="输入音频文件路径 (mp3/wav/m4a 等)")
    parser.add_argument("-o", "--output", default="output.wav", help="输出文件路径 (默认: output.wav)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"中文语音延迟偏移 (秒, 默认: {DEFAULT_DELAY})")
    parser.add_argument("--duck-ratio", type=float, default=DEFAULT_DUCK_RATIO,
                        help=f"中文播放时原声音量比例 (0-1, 默认: {DEFAULT_DUCK_RATIO})")
    parser.add_argument("--chinese-volume", type=float, default=DEFAULT_CHINESE_VOLUME,
                        help=f"中文语音音量 (0-1, 默认: {DEFAULT_CHINESE_VOLUME})")
    parser.add_argument("--keep-temp", action="store_true",
                        help="保留临时文件 (调试用)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 找不到输入文件 {args.input}")
        sys.exit(1)

    temp_dir = tempfile.mkdtemp(prefix="voice_interpreter_")

    try:
        print(f"[1/4] 语音识别中...")
        segments = transcribe(args.input)
        if not segments:
            print("错误: 未识别到语音内容")
            sys.exit(1)
        print(f"  识别到 {len(segments)} 段语音")

        print(f"[2/4] 日→中翻译中...")
        segments = translate(segments)
        for seg in segments:
            print(f"  [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")
            print(f"    → {seg['zh_text']}")

        print(f"[3/4] 中文语音合成中...")
        segments = synthesize(segments, temp_dir)
        print(f"  已生成 {len(segments)} 段中文语音")

        print(f"[4/4] 音频混合中...")
        mix(args.input, segments, args.output,
            delay=args.delay, duck_ratio=args.duck_ratio,
            chinese_volume=args.chinese_volume)
        print(f"  输出文件: {args.output}")

    finally:
        if args.keep_temp:
            print(f"临时文件保留在: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
