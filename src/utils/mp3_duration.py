from mutagen.mp3 import MP3
from pathlib import Path


def save_mp3_durations(directory: str, output_filename: str = "mp3_durations.txt"):
    audio_dir = Path(directory)
    output_path = audio_dir / output_filename
    total_duration = 0
    lines = []

    for mp3_file in sorted(audio_dir.glob("*.mp3")):
        audio = MP3(mp3_file)
        duration = audio.info.length
        total_duration += duration
        line = f"{mp3_file.name}: {duration:.2f}초"
        lines.append(line)
        print(line)

    summary = f"\n총 길이: {total_duration:.2f}초 ({total_duration/60:.2f}분)"
    lines.append(summary)
    print(summary)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n저장 완료: {output_path}")


if __name__ == "__main__":
    save_mp3_durations("outputs/playlists/국립중앙박물관_한국사_완전정복_v2/audio")

