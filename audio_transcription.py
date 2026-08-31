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
import re
import subprocess
import sys
import tempfile

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from openai import OpenAI


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

    def summary(self, success_count: int, fail_count: int) -> None:
        print()
        print(f'   {self.MUTED}{self.RULE}{self.RESET}')
        print(f'    {self.OK}{success_count} transcribed{self.RESET}   {self.FAIL}{fail_count} failed{self.RESET}')

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

    def transcribe_chunk(self, audio_chunk_file: Path) -> str:
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

    def transcribe(self, audio_file: Path) -> str:
        with self.chunker.chunk(audio_file) as chunk_set:
            if not chunk_set.chunk_files:
                message = 'no audio could be read out of this file.'
                raise TranscriptionError(message)

            transcriptions = self.transcribe_chunks(audio_file, chunk_set)

        result = ' '.join(text for text in transcriptions if text)

        if not result:
            message = 'the service returned no words for this audio.'
            raise TranscriptionError(message)

        return result

    def transcribe_chunks(self, audio_file: Path, chunk_set: AudioChunkSet) -> list[str]:
        chunk_count = len(chunk_set)
        transcriptions: list[str] = [''] * chunk_count
        complete_count = 0

        with ThreadPoolExecutor(max_workers=self.workers_max) as thread_executor:
            future_to_index = {
                thread_executor.submit(self.client.transcribe_chunk, chunk_file): index
                for index, chunk_file in enumerate(chunk_set.chunk_files)
            }

            for future in as_completed(future_to_index):
                index: int = future_to_index[future]

                try:
                    transcriptions[index] = future.result()

                except Exception:
                    transcriptions[index] = ''

                complete_count += 1
                self.console.progress(audio_file, complete_count, chunk_count)

        return transcriptions

    def transcribe_to_file(self, audio_file: Path) -> Path:
        output_file = self.free_output_file(audio_file)
        transcription = self.transcribe(audio_file)
        output_file.write_text(self.format_transcription(transcription), encoding='utf-8')

        return output_file


class TranscriptionManager:
    def __init__(self, settings: TranscriptionSettings, console: Console | None = None) -> None:
        self.settings = settings
        self.console = console if console else Console()
        self.fail_count = 0
        self.last_output_file: Path | None = None
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
            output_file = transcriber.transcribe_to_file(audio_file)

        except Exception as error:
            self.console.failure(audio_file, error)
            self.fail_count += 1

        else:
            self.console.success(audio_file, output_file, perf_counter() - start_time)
            self.last_output_file = output_file
            self.success_count += 1

    def report_result_file(self) -> None:
        if self.settings.result_file and self.last_output_file:
            self.settings.result_file.write_text(str(self.last_output_file), encoding='utf-8')

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

        self.console.summary(self.success_count, self.fail_count)
        self.report_result_file()

        return 0


def main() -> int:
    Console.enable_ansi_colors()
    settings = TranscriptionSettings.from_environment()
    manager = TranscriptionManager(settings)

    return manager.run()


if __name__ == '__main__':
    sys.exit(main())
