# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

from __future__ import annotations

import ctypes
import logging
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
from types import TracebackType

from dotenv import load_dotenv
from openai import OpenAI


CHUNK_ATTEMPTS_MAX = 4
CHUNK_RETRY_BACKOFF_SECONDS = 1.5
CHUNK_RETRY_JITTER_SECONDS = 0.5
CHUNK_WORKERS_MAX = 10
CLEANUP_INSTRUCTIONS = (
    'You are cleaning up a raw speech-to-text transcript of a meeting. '
    'Add punctuation, capitalisation and paragraph breaks so that it reads well. '
    'Fix a mis-heard word only when the intended word is obvious. '
    'Never add, drop, shorten or reorder what was said, and never answer or comment on it. '
    'Keep every [inaudible ...] marker exactly where it appears. '
    'Reply with the cleaned transcript only.'
)
OUTPUT_ATTEMPTS_MAX = 999
OUTPUT_MODE_BOTH = 'both'
OUTPUT_MODE_NOTES = 'notes'
OUTPUT_MODE_TRANSCRIPT = 'transcript'
OUTPUT_MODES = (OUTPUT_MODE_BOTH, OUTPUT_MODE_NOTES, OUTPUT_MODE_TRANSCRIPT)
POLISH_ATTEMPTS_MAX = 3
POLISH_CHARACTERS_MAX = 12000
POLISH_RETRY_BACKOFF_SECONDS = 2.0
POLISH_TIMEOUT_SECONDS = 180.0
POLISH_WORKERS_MAX = 4
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
SEGMENT_LENGTH_SECONDS = 30
SUMMARY_INSTRUCTIONS = """
Analyze the provided meeting transcript and generate a structured summary by following these steps:

1. Identify the core purpose of the meeting, major conclusions reached, and open discussions.
2. Extract every explicit commitment, assignment, or follow-up item.

Provide your response in EXACTLY this structure:

SUMMARY
[A brief paragraph summarizing the high-level purpose and outcomes of the conversation.]
- [Key discussion point or decision 1]
- [Key discussion point or decision 2]
- [Key discussion point or decision 3]
- [etc as needed]

ACTION ITEMS
- [Owner/Unassigned]: [Clear description of task]
- [Owner/Unassigned]: [Clear description of task]
- [etc as needed]
(If no tasks exist, output strictly: "- None stated.")
"""

SECTION_INSTRUCTIONS = (
    'You are taking notes on one part of a longer meeting transcript. '
    'Please provide the following: \n' + SUMMARY_INSTRUCTIONS

)
SUPPORTED_AUDIO_EXTENSIONS = ('mp3', 'wav', 'flac', 'mp4', 'mpeg', 'ogg', 'm4a', 'webm')
LOG_PATH = SCRIPT_DIRECTORY.parent / 'mimir.log'
log = logging.getLogger('mimir')


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

    def notes(self, notes_file: Path) -> None:
        print(f'         {self.MUTED}notes{self.RESET} {self.OK}{notes_file.name}{self.RESET}')

    def notes_failure(self, error: Exception) -> None:
        print(f'         {self.WARN}Notes could not be written; the transcript is unchanged.{self.RESET}')
        print(f'         {self.MUTED}{error}{self.RESET}')

    def notes_start(self, audio_file: Path) -> None:
        print(
            f'{self.CLEAR_LINE}{self.MUTED}   [ .. ] writing notes for {audio_file.name}{self.RESET}',
            end='',
            flush=True,
        )

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

        if fail_count or gap_count:
            print(f'    {self.MUTED}details: {LOG_PATH}{self.RESET}')

    def warning(self, message: str) -> None:
        print(f'   {self.WARN}{message}{self.RESET}')


@dataclass(frozen=True)
class TranscriptionSettings:
    api_host: str | None
    api_key: str | None
    audio_model: str
    chunk_workers_max: int
    output_mode: str
    result_file: Path | None
    segment_length_seconds: int
    text_model: str

    @classmethod
    def from_environment(cls) -> TranscriptionSettings:
        load_dotenv(SCRIPT_DIRECTORY / '.env')

        result_path_file = os.getenv('MIMIR_RESULT_FILE')

        return cls(
            api_host=os.getenv('AI_API_HOST'),
            api_key=os.getenv('AI_API_KEY'),
            audio_model=os.getenv('LLM_AUDIO_MODEL', 'stratus.listen'),
            chunk_workers_max=CHUNK_WORKERS_MAX,
            output_mode=os.getenv('MIMIR_OUTPUT_MODE', OUTPUT_MODE_TRANSCRIPT).strip().lower(),
            result_file=Path(result_path_file) if result_path_file else None,
            segment_length_seconds=SEGMENT_LENGTH_SECONDS,
            text_model=os.getenv('LLM_TEXT_MODEL', 'stratus.thinking'),
        )

    @property
    def base_url(self) -> str:
        return f'{self.api_host}/v1'

    @property
    def is_configured(self) -> bool:
        return bool(self.api_host and self.api_key)

    @property
    def keeps_transcript(self) -> bool:
        return self.output_mode in (OUTPUT_MODE_BOTH, OUTPUT_MODE_TRANSCRIPT)

    @property
    def writes_notes(self) -> bool:
        return self.output_mode in (OUTPUT_MODE_BOTH, OUTPUT_MODE_NOTES)


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
            stderr_text = error.stderr.strip() if error.stderr else ''

            if stderr_text:
                log.error('ffmpeg stderr  file=%s\n%s', audio_file.name, stderr_text)

            detail = stderr_text.splitlines()[-1] if stderr_text else ''
            message = f'ffmpeg could not read this file. {detail}'.strip()
            raise TranscriptionError(message) from error

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

                log.warning(
                    'chunk attempt failed  file=%s  attempt=%s/%s  error=%s',
                    audio_chunk_file.name,
                    attempt + 1,
                    CHUNK_ATTEMPTS_MAX,
                    last_error,
                )

            else:
                return transcription

        message = f'{audio_chunk_file.name} failed after {CHUNK_ATTEMPTS_MAX} attempts. {last_error}'
        raise TranscriptionError(message) from last_error


class TranscriptPolisher:
    def __init__(self, settings: TranscriptionSettings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    @staticmethod
    def chunk_lines(lines: list[str], characters_max: int) -> list[str]:
        chunks: list[str] = []
        current_lines: list[str] = []
        current_length = 0

        for line in lines:
            if current_lines and current_length + len(line) > characters_max:
                chunks.append('\n'.join(current_lines))
                current_lines = []
                current_length = 0

            current_lines.append(line)
            current_length += len(line) + 1

        if current_lines:
            chunks.append('\n'.join(current_lines))

        return chunks

    def request_completion(self, instructions: str, content: str) -> str:
        system_message = {'role': 'system', 'content': instructions}
        user_message = {'role': 'user', 'content': content}
        messages = [system_message, user_message]

        completion = self.client.chat.completions.create(
            model=self.settings.text_model,
            messages=messages,
            timeout=POLISH_TIMEOUT_SECONDS,
        )

        message_content = completion.choices[0].message.content

        return message_content if message_content else ''

    def complete(self, instructions: str, content: str) -> str:
        last_error: Exception | None = None

        for attempt in range(POLISH_ATTEMPTS_MAX):
            if attempt:
                sleep(POLISH_RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1))

            try:
                completion_text = self.request_completion(instructions, content)

            except Exception as error:
                last_error = error

                log.warning(
                    'text model attempt failed  attempt=%s/%s  error=%s',
                    attempt + 1,
                    POLISH_ATTEMPTS_MAX,
                    last_error,
                )

            else:
                return completion_text

        message = f'the text model failed after {POLISH_ATTEMPTS_MAX} attempts. {last_error}'
        raise TranscriptionError(message) from last_error

    def complete_many(self, instructions: str, contents: list[str]) -> list[str]:
        completion_texts: list[str] = [''] * len(contents)

        with ThreadPoolExecutor(max_workers=POLISH_WORKERS_MAX) as thread_executor:
            future_to_index = {
                thread_executor.submit(self.complete, instructions, content): index
                for index, content in enumerate(contents)
            }

            for future in as_completed(future_to_index):
                index: int = future_to_index[future]
                completion_texts[index] = future.result().strip()

        return completion_texts

    def summarize(self, cleaned_chunks: list[str]) -> str:
        if len(cleaned_chunks) == 1:
            return self.complete(SUMMARY_INSTRUCTIONS, cleaned_chunks[0]).strip()

        section_notes = self.complete_many(SECTION_INSTRUCTIONS, cleaned_chunks)
        joined_notes = '\n'.join(text for text in section_notes if text)

        return self.complete(SUMMARY_INSTRUCTIONS, joined_notes).strip()

    def polish(self, transcript_text: str) -> TranscriptNotes:
        chunks = self.chunk_lines(transcript_text.splitlines(), POLISH_CHARACTERS_MAX)
        cleaned_chunks = self.complete_many(CLEANUP_INSTRUCTIONS, chunks)
        cleaned_text = '\n\n'.join(text for text in cleaned_chunks if text)

        if not cleaned_text:
            message = 'the text model returned no cleaned transcript.'
            raise TranscriptionError(message)

        summary_text = self.summarize(cleaned_chunks)

        if not summary_text:
            message = 'the text model returned no summary.'
            raise TranscriptionError(message)

        return TranscriptNotes(cleaned_text=cleaned_text, summary_text=summary_text)


@dataclass(frozen=True)
class ChunkTranscriptions:
    gap_count: int
    texts: list[str]


@dataclass(frozen=True)
class TranscriptNotes:
    cleaned_text: str
    summary_text: str


@dataclass(frozen=True)
class NotesOutput:
    error: Exception | None
    notes_file: Path | None


@dataclass(frozen=True)
class TranscriptionOutput:
    gap_count: int
    notes_error: Exception | None
    notes_file: Path | None
    transcript_file: Path | None


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
            keep_transcript: bool = True,
            polisher: TranscriptPolisher | None = None,
            workers_max: int = CHUNK_WORKERS_MAX,
    ) -> None:
        self.chunker = chunker
        self.client = client
        self.console = console
        self.keep_transcript = keep_transcript
        self.polisher = polisher
        self.workers_max = workers_max

    @staticmethod
    def format_notes(audio_file: Path, notes: TranscriptNotes) -> str:
        sections = [
            'MIMIR NOTES',
            audio_file.name,
            '',
            'AI wrote these notes from the transcript. Check them before you rely on them.',
            '',
            notes.summary_text,
            '',
            'CLEANED TRANSCRIPT',
            '',
            notes.cleaned_text,
            '',
        ]

        return '\n'.join(sections)

    @staticmethod
    def format_transcription(transcription: str) -> str:
        return re.sub(r'([.!?])\s+', r'\1\n', transcription)

    @staticmethod
    def free_output_file(audio_file: Path, name_suffix: str) -> Path:
        base_name = audio_file.stem.lower().replace(' ', '_')
        output_file = audio_file.with_name(f'{base_name}_{name_suffix}.txt')
        attempt = 0

        while output_file.exists():
            attempt += 1

            if attempt > OUTPUT_ATTEMPTS_MAX:
                message = f'too many existing files named {base_name}_{name_suffix}.'
                raise TranscriptionError(message)

            output_file = audio_file.with_name(f'{base_name}_{name_suffix} ({attempt}).txt')

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
                    log.exception(
                        'chunk failed  file=%s  piece=%s of %s',
                        audio_file.name,
                        index + 1,
                        chunk_count,
                    )

                    texts[index] = self.inaudible_marker(index)
                    gap_count += 1

                complete_count += 1
                self.console.progress(audio_file, complete_count, chunk_count)

        return ChunkTranscriptions(gap_count=gap_count, texts=texts)

    def transcribe_to_file(self, audio_file: Path) -> TranscriptionOutput:
        transcript_file = self.free_output_file(audio_file, 'transcript')
        result = self.transcribe(audio_file)
        transcript_text = self.format_transcription(result.text)
        transcript_file.write_text(transcript_text, encoding='utf-8')
        notes_output = self.write_notes(audio_file, transcript_text)
        kept_transcript_file: Path | None = transcript_file

        if notes_output.notes_file and not self.keep_transcript:
            transcript_file.unlink(missing_ok=True)
            kept_transcript_file = None

        return TranscriptionOutput(
            gap_count=result.gap_count,
            notes_error=notes_output.error,
            notes_file=notes_output.notes_file,
            transcript_file=kept_transcript_file,
        )

    def write_notes(self, audio_file: Path, transcript_text: str) -> NotesOutput:
        if self.polisher is None:
            return NotesOutput(error=None, notes_file=None)

        self.console.notes_start(audio_file)

        try:
            notes = self.polisher.polish(transcript_text)

        except Exception as error:
            log.exception('notes failed  file=%s', audio_file.name)

            return NotesOutput(error=error, notes_file=None)

        else:
            notes_file = self.free_output_file(audio_file, 'notes')
            notes_file.write_text(self.format_notes(audio_file, notes), encoding='utf-8')

            return NotesOutput(error=None, notes_file=notes_file)


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
        polisher = TranscriptPolisher(self.settings) if self.settings.writes_notes else None

        return AudioFileTranscriber(
            chunker=AudioChunker(self.settings.segment_length_seconds),
            client=TranscriptionClient(self.settings),
            console=self.console,
            keep_transcript=self.settings.keeps_transcript,
            polisher=polisher,
            workers_max=self.settings.chunk_workers_max,
        )

    def process(self, transcriber: AudioFileTranscriber, audio_file: Path) -> None:
        start_time = perf_counter()
        self.console.start(audio_file)
        log.info('transcribe start  file=%s', audio_file.name)

        try:
            output = transcriber.transcribe_to_file(audio_file)

        except Exception as error:
            log.exception('transcribe failed  file=%s', audio_file.name)
            self.console.failure(audio_file, error)
            self.fail_count += 1

        else:
            written_files = [file for file in (output.transcript_file, output.notes_file) if file]
            elapsed_seconds = perf_counter() - start_time
            self.console.success(audio_file, written_files[0], elapsed_seconds)
            self.output_files.extend(written_files)
            self.success_count += 1

            log.info(
                'transcribe ok  file=%s  output=%s  seconds=%.0f',
                audio_file.name,
                written_files[0].name,
                elapsed_seconds,
            )

            if len(written_files) > 1:
                self.console.notes(written_files[1])

            if output.notes_error:
                self.console.notes_failure(output.notes_error)

            if output.gap_count:
                gap_seconds = output.gap_count * self.settings.segment_length_seconds
                self.console.gaps(output.gap_count, gap_seconds)
                log.warning(
                    'transcribe gaps  file=%s  gap_count=%s  gap_seconds=%s',
                    audio_file.name,
                    output.gap_count,
                    gap_seconds,
                )

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
            log.error('no API settings were found. %s', detail)

            return 1

        if self.settings.output_mode not in OUTPUT_MODES:
            detail = f'MIMIR_OUTPUT_MODE must be one of: {OUTPUT_MODES}'
            self.console.error(f'Unknown output mode: {self.settings.output_mode}', detail)
            log.error('unknown output mode: %s  %s', self.settings.output_mode, detail)

            return 1

        audio_files = self.collect_audio_files()
        log.info('queued %s file(s)', len(audio_files))

        if not audio_files:
            self.console.warning('No audio files to transcribe.')
            log.warning('no audio files to transcribe')

            return 0

        transcriber = self.build_transcriber()

        for audio_file in audio_files:
            self.process(transcriber, audio_file)

        self.console.summary(self.success_count, self.fail_count, self.gap_file_count, self.gap_count)
        self.report_result_file()

        return 0


def configure_logging() -> None:
    if log.handlers:
        return

    if LOG_PATH.exists() and LOG_PATH.stat().st_size:
        with LOG_PATH.open('a', encoding='utf-8') as log_file:
            log_file.write('\n')

    formatter = logging.Formatter(
        fmt='%(asctime)s  %(levelname)-8s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    try:
        handler = logging.FileHandler(LOG_PATH, encoding='utf-8')

    except OSError:
        print(f'   could not write log file: {LOG_PATH}', file=sys.stderr)

        return

    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    logging.captureWarnings(True)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.WARNING)
    sys.excepthook = unhandled_exception


def main() -> int:
    configure_logging()
    Console.enable_ansi_colors()
    settings = TranscriptionSettings.from_environment()
    manager = TranscriptionManager(settings)

    log.info(
        'session start  python=%s  output_mode=%s  audio_model=%s  text_model=%s  host=%s  key=%s',
        sys.version.split()[0],
        settings.output_mode,
        settings.audio_model,
        settings.text_model,
        settings.api_host or '(missing)',
        'set' if settings.api_key else 'missing',
    )

    exit_code = manager.run()

    log.info(
        'session end  transcribed=%s  failed=%s  gaps=%s',
        manager.success_count,
        manager.fail_count,
        manager.gap_count,
    )

    return exit_code


def unhandled_exception(
    exception_type: type[BaseException],
    exception: BaseException,
    traceback_object: TracebackType | None,
) -> None:
    log.exception(
        'unhandled exception',
        exc_info=(exception_type, exception, traceback_object),
    )

    sys.__excepthook__(exception_type, exception, traceback_object)


if __name__ == '__main__':
    sys.exit(main())
