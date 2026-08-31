import os
import subprocess
import tempfile
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

from dotenv import load_dotenv
from openai import OpenAI

SUPPORTED_AUDIO_EXTENSIONS = ('mp3', 'wav', 'flac', 'mp4', 'mpeg', 'ogg')

load_dotenv(Path.cwd() / '.env')

client = OpenAI(
    api_key=os.getenv('AI_API_KEY'),
    base_url=f'{os.getenv("AI_API_HOST")}/v1'
)


def chunk_audio_file(
        audio_file: Path,
        segment_length_seconds: int = 30
) -> list[Path]:
    audio_extension = audio_file.suffix[1:]

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
        raise Exception(f'ffmpeg error: {e.stderr}')

    except FileNotFoundError:
        raise Exception('ffmpeg not found. Install ffmpeg: https://ffmpeg.org/download.html')


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
    file_size_mb = audio_file.stat().st_size / (1024 * 1024)

    print(f'Transcribing {audio_file.name} ({file_size_mb:.1f}MB) ...')
    audio_chunk_files = chunk_audio_file(audio_file, segment_length_seconds=30)

    print(f'0.0% (0 / {len(audio_chunk_files)} audio chunks transcribed)', end='\r')

    transcriptions = [None] * len(audio_chunk_files)

    with ThreadPoolExecutor(max_workers=10) as thread_executor:
        future_to_index = {
            thread_executor.submit(transcribe_audio_chunk, audio_chunk_file): i
            for i, audio_chunk_file in enumerate(audio_chunk_files)
        }

        complete_count = 0

        for future in as_completed(future_to_index):
            index: int = future_to_index[future]

            try:
                text = future.result()
                transcriptions[index] = text
                complete_count += 1
                percentage_complete = (complete_count / len(audio_chunk_files) * 100)
                print(
                    f'{percentage_complete:.1f}% ({complete_count + 1} / {len(audio_chunk_files)} audio chunks transcribed)',
                    end='\r')

            except Exception as e:
                print(f'Error on chunk {index + 1}: {e}')
                transcriptions[index] = ''

    if audio_chunk_files:
        temp_directory = audio_chunk_files[0].parent

        for audio_chunk_file in audio_chunk_files:
            audio_chunk_file.unlink(missing_ok=True)

        temp_directory.rmdir()

    result = ' '.join(text for text in transcriptions if text)

    if result:
        return result
    else:
        message = 'No transcription was created'
        raise Exception(message)


def main():
    audio_files = []

    for audio_extension in SUPPORTED_AUDIO_EXTENSIONS:
        audio_files.extend(list(Path.cwd().glob(f'*.{audio_extension}')))

    if not audio_files:
        print('No audio files found in the directory.\n')
        return

    print(f'Found {len(audio_files)} audio file(s)\n')

    for audio_file in audio_files:
        start_time = perf_counter()

        transcription_output_file = audio_file.with_name(
            f'{audio_file.stem.lower().replace(" ", "_")}_transcript.txt'
        )

        if transcription_output_file.exists():
            print(f'Skipping {audio_file.name} ...')
            print(f'Transcription already exists ({transcription_output_file.name})\n')
            continue

        try:
            with open(transcription_output_file, 'w', encoding='utf-8') as f:
                transcription = transcribe_audio(audio_file)

                formatted = re.sub(r'([.!?])\s+', r'\1\n', transcription)

                f.write(formatted)

                print(f'Took {(perf_counter() - start_time):.1f} seconds to transcribe' + ' ' * 32)
                print(f'Saved to {transcription_output_file.name}\n')

        except Exception as e:
            print(f'Error transcribing {audio_file.name}: {e}\n')


if __name__ == '__main__':
    main()
