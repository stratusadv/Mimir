# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

from __future__ import annotations

import ctypes
import os
import random
import re
import subprocess
import sys
import tempfile

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter, sleep

from dotenv import load_dotenv
from openai import OpenAI


CHUNK_ATTEMPTS_MAX = 4
CHUNK_RETRY_BACKOFF_SECONDS = 1.5
CHUNK_RETRY_JITTER_SECONDS = 0.5
CHUNK_WORKERS_MAX = 10
OUTPUT_ATTEMPTS_MAX = 999
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
SEGMENT_LENGTH_SECONDS = 30
SUPPORTED_AUDIO_EXTENSIONS = ('mp3', 'wav', 'flac', 'mp4', 'mpeg', 'ogg', 'm4a', 'webm')


class TranscriptionError(Exception):
    pass


class Console:
    ACCENT = '\033[96m'
    CLEAR_LINE = '\033[2K\033[G'
    FAIL = '\033[91m'
    MUTED = '\033[90m'
    OK = '\033[92m'
    RESET = '\033[0m'
    RULE = '--------------------------------------------------------------------'
    WARN = '\033[93m'

    @staticmethod
    def enable_ansi_colors() -> None:
        if os.name != 'nt':
            return

        kernel32 = ctypes.windll.kernel32
        _ = kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    def error(self, message: str, detail: str = '') -> None:
        print(f'   {self.FAIL}[ERROR]{self.RESET} {message}')

        if detail:
            print(f'   {self.MUTED}{detail}{self.RESET}')

    def gaps(self, gap_count: int, gap_seconds: int) -> None:
        piece_label = 'piece' if gap_count == 1 else 'pieces'

        print(
            f'         {self.WARN}{gap_count} {piece_label} could not be transcribed; '
            f'{gap_seconds} seconds marked [inaudible] in the transcript{self.RESET}'
        )

    def failure(self, audio_file: Path, error: Exception) -> None:
        print(f'{self.CLEAR_LINE}   {self.FAIL}[FAIL]{self.RESET} {audio_file.name}')
        print(f'         {self.MUTED}{error}{self.RESET}')

    def progress(self, audio_file: Path, complete_count: int, chunk_count: int) -> None:
        percentage_complete = complete_count / chunk_count * 100

        print(
            f'{self.CLEAR_LINE}{self.MUTED}   [ {percentage_complete:3.0f}% ] '
            f'{audio_file.name} {self.RESET}{self.MUTED}'
            f'({complete_count} of {chunk_count} pieces){self.RESET}',
            end='',
            flush=True,
        )

    def start(self, audio_file: Path) -> None:
        print(f'{self.MUTED}   [  0% ] {audio_file.name}{self.RESET}', end='', flush=True)

    def success(self, audio_file: Path, output_file: Path, elapsed_seconds: float) -> None:
        print(
            f'{self.CLEAR_LINE}   {self.OK}[ OK ]{self.RESET} {audio_file.name} '
            f'{self.MUTED}->{self.RESET} {self.OK}{output_file.name}{self.RESET}'
        )

        print(f'         {self.MUTED}{elapsed_seconds:.0f} seconds{self.RESET}')

    def summary(self, success_count: int, fail_count: int, gap_file_count: int, gap_count: int) -> None:
        print()
        print(f'   {self.MUTED}{self.RULE}{self.RESET}')
        print(f'    {self.OK}{success_count} transcribed{self.RESET}   {self.FAIL}{fail_count} failed{self.RESET}')

        if gap_count:
            file_label = 'file' if gap_file_count == 1 else 'files'
            piece_label = 'piece' if gap_count == 1 else 'pieces'

            print(
                f'    {self.WARN}{gap_count} audio {piece_label} missing across '
                f'{gap_file_count} {file_label}; search transcripts for [inaudible]{self.RESET}'
            )

    def warning(self, message: str) -> None:
        print(f'   {self.WARN}{message}{self.RESET}')


@dataclass(frozen=True)
class TranscriptionSettings:
    api_host: str | None
    api_key: str | None
    audio_model: str
    chunk_workers_max: int
    result_file: Path | None
    segment_length_seconds: int

    @classmethod
    def from_environment(cls) -> TranscriptionSettings:
        load_dotenv(SCRIPT_DIRECTORY / '.env')

        result_path_file = os.getenv('MIMIR_RESULT_FILE')

        return cls(
            api_host=os.getenv('AI_API_HOST'),
            api_key=os.getenv('AI_API_KEY'),
            audio_model=os.getenv('LLM_AUDIO_MODEL', 'stratus.listen'),
            chunk_workers_max=CHUNK_WORKERS_MAX,
            result_file=Path(result_path_file) if result_path_file else None,
            segment_length_seconds=SEGMENT_LENGTH_SECONDS,
        )

    @property
    def base_url(self) -> str:
        return f'{self.api_host}/v1'

    @property
    def is_configured(self) -> bool:
        return bool(self.api_host and self.api_key)


class AudioChunkSet:
    def __init__(self, chunk_files: list[Path], temp_directory: Path) -> None:
        self.chunk_files = chunk_files
        self.temp_directory = temp_directory

    def __enter__(self) -> AudioChunkSet:
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self.discard()

    def __len__(self) -> int:
        return len(self.chunk_files)

    def discard(self) -> None:
        for chunk_file in self.chunk_files:
            chunk_file.unlink(missing_ok=True)

        if self.temp_directory.exists():
            self.temp_directory.rmdir()


class AudioChunker:
    def __init__(self, segment_length_seconds: int = SEGMENT_LENGTH_SECONDS) -> None:
        self.segment_length_seconds = segment_length_seconds

    @staticmethod
    def audio_extension(audio_file: Path) -> str:
        audio_extension = audio_file.suffix[1:].lower()

        if audio_extension not in SUPPORTED_AUDIO_EXTENSIONS:
            message = f'{audio_file.name} has unsupported extension, choices are: {SUPPORTED_AUDIO_EXTENSIONS}'
            raise TranscriptionError(message)

        return audio_extension

    def chunk(self, audio_file: Path) -> AudioChunkSet:
        audio_extension = self.audio_extension(audio_file)
        temp_directory = Path(tempfile.mkdtemp())
        output_pattern = temp_directory / f'chunk_%03d.{audio_extension}'

        command = [
            'ffmpeg',
            '-i', str(audio_file),
            '-f', 'segment',
            '-segment_time', str(self.segment_length_seconds),
            '-c', 'copy',
            '-reset_timestamps', '1',
            str(output_pattern),
        ]

        try:
            _ = subprocess.run(command, capture_output=True, text=True, check=True)

        except subprocess.CalledProcessError as error:
            temp_directory.rmdir()
            detail = error.stderr.strip().splitlines()[-1] if error.stderr and error.stderr.strip() else ''
            message = f'ffmpeg could not read this file. {detail}'.strip()

            raise TranscriptionError(message)

        except FileNotFoundError:
            temp_directory.rmdir()
            message = 'ffmpeg was not found. Close this window and run transcribe.bat again.'

            raise TranscriptionError(message)

        else:
            chunk_files = sorted(temp_directory.glob(f'chunk_*.{audio_extension}'))
            return AudioChunkSet(chunk_files, temp_directory)


class TranscriptionClient:
    def __init__(self, settings: TranscriptionSettings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    def request_chunk_transcription(self, audio_chunk_file: Path) -> str:
        with open(audio_chunk_file, 'rb') as audio_file:
            transcription = self.client.audio.transcriptions.create(
                model=self.settings.audio_model,
                file=audio_file,
                timeout=60.0,
            )

        if hasattr(transcription, 'error') and transcription.error:
            message = f'API Error: {transcription.error.get("message", "Unknown error")}'
            raise TranscriptionError(message)

        return transcription.text if transcription.text else ''

    def transcribe_chunk(self, audio_chunk_file: Path) -> str:
        last_error: Exception | None = None

        for attempt in range(CHUNK_ATTEMPTS_MAX):
            if attempt:
                backoff_seconds = CHUNK_RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1)
                sleep(backoff_seconds + random.uniform(0.0, CHUNK_RETRY_JITTER_SECONDS))

            try:
                transcription = self.request_chunk_transcription(audio_chunk_file)

            except Exception as error:
                last_error = error

            else:
                return transcription

        message = f'{audio_chunk_file.name} failed after {CHUNK_ATTEMPTS_MAX} attempts. {last_error}'

        raise TranscriptionError(message)


@dataclass(frozen=True)
class ChunkTranscriptions:
    gap_count: int
    texts: list[str]


@dataclass(frozen=True)
class TranscriptionOutput:
    gap_count: int
    output_file: Path


@dataclass(frozen=True)
class TranscriptionResult:
    gap_count: int
    text: str


class AudioFileTranscriber:
    def __init__(
            self,
            chunker: AudioChunker,
            client: TranscriptionClient,
            console: Console,
            workers_max: int = CHUNK_WORKERS_MAX,
    ) -> None:
        self.chunker = chunker
        self.client = client
        self.console = console
        self.workers_max = workers_max

    @staticmethod
    def format_transcription(transcription: str) -> str:
        return re.sub(r'([.!?])\s+', r'\1\n', transcription)

    @staticmethod
    def free_output_file(audio_file: Path) -> Path:
        base_name = audio_file.stem.lower().replace(' ', '_')
        output_file = audio_file.with_name(f'{base_name}_transcript.txt')
        attempt = 0

        while output_file.exists():
            attempt += 1

            if attempt > OUTPUT_ATTEMPTS_MAX:
                message = 'too many existing transcripts with that name.'
                raise TranscriptionError(message)

            output_file = audio_file.with_name(f'{base_name}_transcript ({attempt}).txt')

        return output_file

    def inaudible_marker(self, chunk_index: int) -> str:
        segment_length_seconds = self.chunker.segment_length_seconds
        start_seconds = chunk_index * segment_length_seconds
        end_seconds = start_seconds + segment_length_seconds

        return f'[inaudible {self.timestamp_label(start_seconds)}-{self.timestamp_label(end_seconds)}]'

    @staticmethod
    def timestamp_label(total_seconds: int) -> str:
        hours, remainder_seconds = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder_seconds, 60)

        if hours:
            return f'{hours}:{minutes:02d}:{seconds:02d}'

        return f'{minutes:02d}:{seconds:02d}'

    def transcribe(self, audio_file: Path) -> TranscriptionResult:
        with self.chunker.chunk(audio_file) as chunk_set:
            if not chunk_set.chunk_files:
                message = 'no audio could be read out of this file.'
                raise TranscriptionError(message)

            chunk_transcriptions = self.transcribe_chunks(audio_file, chunk_set)

        if chunk_transcriptions.gap_count == len(chunk_transcriptions.texts):
            message = f'every piece of audio failed to transcribe ({chunk_transcriptions.gap_count} pieces).'

            raise TranscriptionError(message)

        text = ' '.join(text for text in chunk_transcriptions.texts if text)

        if not text:
            message = 'the service returned no words for this audio.'
            raise TranscriptionError(message)

        return TranscriptionResult(gap_count=chunk_transcriptions.gap_count, text=text)

    def transcribe_chunks(self, audio_file: Path, chunk_set: AudioChunkSet) -> ChunkTranscriptions:
        chunk_count = len(chunk_set)
        texts: list[str] = [''] * chunk_count
        complete_count = 0
        gap_count = 0

        with ThreadPoolExecutor(max_workers=self.workers_max) as thread_executor:
            future_to_index = {
                thread_executor.submit(self.client.transcribe_chunk, chunk_file): index
                for index, chunk_file in enumerate(chunk_set.chunk_files)
            }

            for future in as_completed(future_to_index):
                index: int = future_to_index[future]

                try:
                    texts[index] = future.result()

                except Exception:
                    texts[index] = self.inaudible_marker(index)
                    gap_count += 1

                complete_count += 1
                self.console.progress(audio_file, complete_count, chunk_count)

        return ChunkTranscriptions(gap_count=gap_count, texts=texts)

    def transcribe_to_file(self, audio_file: Path) -> TranscriptionOutput:
        output_file = self.free_output_file(audio_file)
        result = self.transcribe(audio_file)
        output_file.write_text(self.format_transcription(result.text), encoding='utf-8')

        return TranscriptionOutput(gap_count=result.gap_count, output_file=output_file)


class TranscriptionManager:
    def __init__(self, settings: TranscriptionSettings, console: Console | None = None) -> None:
        self.settings = settings
        self.console = console if console else Console()
        self.fail_count = 0
        self.gap_count = 0
        self.gap_file_count = 0
        self.output_files: list[Path] = []
        self.success_count = 0

    @staticmethod
    def collect_audio_files() -> list[Path]:
        if len(sys.argv) > 1:
            list_file = Path(sys.argv[1])
            lines = list_file.read_text(encoding='utf-8').splitlines()

            return [Path(line.strip()) for line in lines if line.strip()]

        audio_files = []

        for audio_extension in SUPPORTED_AUDIO_EXTENSIONS:
            audio_files.extend(list(Path.cwd().glob(f'*.{audio_extension}')))

        return audio_files

    def build_transcriber(self) -> AudioFileTranscriber:
        return AudioFileTranscriber(
            chunker=AudioChunker(self.settings.segment_length_seconds),
            client=TranscriptionClient(self.settings),
            console=self.console,
            workers_max=self.settings.chunk_workers_max,
        )

    def process(self, transcriber: AudioFileTranscriber, audio_file: Path) -> None:
        start_time = perf_counter()
        self.console.start(audio_file)

        try:
            output = transcriber.transcribe_to_file(audio_file)

        except Exception as error:
            self.console.failure(audio_file, error)
            self.fail_count += 1

        else:
            self.console.success(audio_file, output.output_file, perf_counter() - start_time)
            self.output_files.append(output.output_file)
            self.success_count += 1

            if output.gap_count:
                self.console.gaps(output.gap_count, output.gap_count * self.settings.segment_length_seconds)
                self.gap_count += output.gap_count
                self.gap_file_count += 1

    def report_result_file(self) -> None:
        if not (self.settings.result_file and self.output_files):
            return

        lines = '\n'.join(str(output_file) for output_file in self.output_files)
        self.settings.result_file.write_text(lines, encoding='utf-8')

    def run(self) -> int:
        if not self.settings.is_configured:
            detail = f'Expected a .env file beside the script: {SCRIPT_DIRECTORY}'
            self.console.error('No API settings were found.', detail)

            return 1

        audio_files = self.collect_audio_files()

        if not audio_files:
            self.console.warning('No audio files to transcribe.')

            return 0

        transcriber = self.build_transcriber()

        for audio_file in audio_files:
            self.process(transcriber, audio_file)

        self.console.summary(self.success_count, self.fail_count, self.gap_file_count, self.gap_count)
        self.report_result_file()

        return 0


def main() -> int:
    Console.enable_ansi_colors()
    settings = TranscriptionSettings.from_environment()
    manager = TranscriptionManager(settings)

    return manager.run()


if __name__ == '__main__':
    sys.exit(main())
