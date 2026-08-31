# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import ctypes
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from openai import OpenAI

SUPPORTED_AUDIO_EXTENSIONS = ('mp3', 'wav', 'flac', 'mp4', 'mpeg', 'ogg', 'm4a', 'webm')

SCRIPT_DIRECTORY = Path(__file__).resolve().parent

C_ACCENT = '\033[96m'
C_FAIL = '\033[91m'
C_MUTED = '\033[90m'
C_OK = '\033[92m'
C_RESET = '\033[0m'
C_WARN = '\033[93m'
CLEAR_LINE = '\033[2K\033[G'

load_dotenv(SCRIPT_DIRECTORY / '.env')

client = OpenAI(
    api_key=os.getenv('AI_API_KEY'),
    base_url=f'{os.getenv("AI_API_HOST")}/v1'
)


def enable_ansi_colors() -> None:
    if os.name != 'nt':
        return

    kernel32 = ctypes.windll.kernel32
    _ = kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def chunk_audio_file(
        audio_file: Path,
        segment_length_seconds: int = 30
) -> list[Path]:
    audio_extension = audio_file.suffix[1:].lower()

    if audio_extension not in SUPPORTED_AUDIO_EXTENSIONS:
        message = f'{audio_file.name} has unsupported extension, choices are: {SUPPORTED_AUDIO_EXTENSIONS}'
        raise ValueError(message)

    temp_directory = Path(tempfile.mkdtemp())
    output_pattern = temp_directory / f'chunk_%03d.{audio_extension}'

    cmd = [
        'ffmpeg',
        '-i', str(audio_file),
        '-f', 'segment',
        '-segment_time', str(segment_length_seconds),
        '-c', 'copy',
        '-reset_timestamps', '1',
        str(output_pattern)
    ]

    try:
        _ = subprocess.run(cmd, capture_output=True, text=True, check=True)
        chunks = sorted(temp_directory.glob(f'chunk_*.{audio_extension}'))
        return chunks

    except subprocess.CalledProcessError as e:
        detail = e.stderr.strip().splitlines()[-1] if e.stderr and e.stderr.strip() else ''
        raise Exception(f'ffmpeg could not read this file. {detail}'.strip())

    except FileNotFoundError:
        raise Exception('ffmpeg was not found. Close this window and run transcribe.bat again.')


def transcribe_audio_chunk(audio_chunk_file: Path) -> str:
    with open(audio_chunk_file, 'rb') as audio_file:
        transcription = client.audio.transcriptions.create(
            model=os.getenv('LLM_AUDIO_MODEL', 'stratus.listen'),
            file=audio_file,
            timeout=60.0,
        )

    if hasattr(transcription, 'error') and transcription.error:
        error_msg = transcription.error.get('message', 'Unknown error')
        raise Exception(f'API Error: {error_msg}')

    return transcription.text if transcription.text else ''


def transcribe_audio(audio_file: Path) -> str:
    audio_chunk_files = chunk_audio_file(audio_file, segment_length_seconds=30)

    if not audio_chunk_files:
        raise Exception('no audio could be read out of this file.')

    transcriptions = [None] * len(audio_chunk_files)
    chunk_count = len(audio_chunk_files)

    with ThreadPoolExecutor(max_workers=10) as thread_executor:
        future_to_index = {
            thread_executor.submit(transcribe_audio_chunk, audio_chunk_file): i
            for i, audio_chunk_file in enumerate(audio_chunk_files)
        }

        complete_count = 0

        for future in as_completed(future_to_index):
            index: int = future_to_index[future]

            try:
                transcriptions[index] = future.result()

            except Exception:
                transcriptions[index] = ''

            complete_count += 1
            percentage_complete = complete_count / chunk_count * 100
            print(
                f'{CLEAR_LINE}{C_MUTED}   [ {percentage_complete:3.0f}% ] '
                f'{audio_file.name} {C_RESET}{C_MUTED}({complete_count} of {chunk_count} pieces){C_RESET}',
                end='',
                flush=True
            )

    temp_directory = audio_chunk_files[0].parent

    for audio_chunk_file in audio_chunk_files:
        audio_chunk_file.unlink(missing_ok=True)

    temp_directory.rmdir()

    result = ' '.join(text for text in transcriptions if text)

    if not result:
        raise Exception('the service returned no words for this audio.')

    return result


def find_free_output_file(audio_file: Path) -> Path:
    base_name = audio_file.stem.lower().replace(' ', '_')
    output_file = audio_file.with_name(f'{base_name}_transcript.txt')
    attempt = 0

    while output_file.exists():
        attempt += 1

        if attempt > 999:
            raise Exception('too many existing transcripts with that name.')

        output_file = audio_file.with_name(f'{base_name}_transcript ({attempt}).txt')

    return output_file


def collect_audio_files() -> list[Path]:
    if len(sys.argv) > 1:
        list_file = Path(sys.argv[1])
        lines = list_file.read_text(encoding='utf-8').splitlines()
        return [Path(line.strip()) for line in lines if line.strip()]

    audio_files = []

    for audio_extension in SUPPORTED_AUDIO_EXTENSIONS:
        audio_files.extend(list(Path.cwd().glob(f'*.{audio_extension}')))

    return audio_files


def main():
    enable_ansi_colors()

    if not os.getenv('AI_API_KEY') or not os.getenv('AI_API_HOST'):
        print(f'   {C_FAIL}[ERROR]{C_RESET} No API settings were found.')
        print(f'   {C_MUTED}Expected a .env file beside the script: {SCRIPT_DIRECTORY}{C_RESET}')
        sys.exit(1)

    audio_files = collect_audio_files()

    if not audio_files:
        print(f'   {C_WARN}No audio files to transcribe.{C_RESET}')
        return

    fail_count = 0
    last_output_file = None
    success_count = 0

    for audio_file in audio_files:
        start_time = perf_counter()

        print(f'{C_MUTED}   [  0% ] {audio_file.name}{C_RESET}', end='', flush=True)

        try:
            output_file = find_free_output_file(audio_file)
            transcription = transcribe_audio(audio_file)
            formatted = re.sub(r'([.!?])\s+', r'\1\n', transcription)
            output_file.write_text(formatted, encoding='utf-8')

            elapsed_seconds = perf_counter() - start_time
            print(f'{CLEAR_LINE}   {C_OK}[ OK ]{C_RESET} {audio_file.name} {C_MUTED}->{C_RESET} {C_OK}{output_file.name}{C_RESET}')
            print(f'         {C_MUTED}{elapsed_seconds:.0f} seconds{C_RESET}')

            last_output_file = output_file
            success_count += 1

        except Exception as e:
            print(f'{CLEAR_LINE}   {C_FAIL}[FAIL]{C_RESET} {audio_file.name}')
            print(f'         {C_MUTED}{e}{C_RESET}')
            fail_count += 1

    print()
    print(f'   {C_MUTED}--------------------------------------------------------------------{C_RESET}')
    print(f'    {C_OK}{success_count} transcribed{C_RESET}   {C_FAIL}{fail_count} failed{C_RESET}')

    result_path_file = os.getenv('MIMIR_RESULT_FILE')

    if result_path_file and last_output_file:
        Path(result_path_file).write_text(str(last_output_file), encoding='utf-8')


if __name__ == '__main__':
    main()
