from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile

from pathlib import Path
from types import TracebackType

from constants import SEGMENT_LENGTH_SECONDS, SUPPORTED_AUDIO_EXTENSIONS
from errors import TranscriptionError


log = logging.getLogger('mimir')


class AudioChunkSet:
    def __init__(self, chunk_files: list[Path], temp_directory: Path) -> None:
        self.chunk_files = chunk_files
        self.temp_directory = temp_directory

    def __enter__(self) -> AudioChunkSet:
        return self

    def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception_value: BaseException | None,
            traceback: TracebackType | None,
    ) -> None:
        self.discard()

    def __len__(self) -> int:
        return len(self.chunk_files)

    def discard(self) -> None:
        shutil.rmtree(self.temp_directory, ignore_errors=True)


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

        owned = False

        try:
            _ = subprocess.run(command, capture_output=True, text=True, check=True)

        except subprocess.CalledProcessError as error:
            stderr_text = error.stderr.strip() if error.stderr else ''

            if stderr_text:
                log.error('ffmpeg stderr  file=%s\n%s', audio_file.name, stderr_text)

            detail = stderr_text.splitlines()[-1] if stderr_text else ''
            message = f'ffmpeg could not read this file. {detail}'.strip()
            raise TranscriptionError(message) from error

        except FileNotFoundError:
            message = 'ffmpeg was not found. Close this window and run transcribe.bat again.'

            raise TranscriptionError(message)

        else:
            chunk_files = sorted(temp_directory.glob(f'chunk_*.{audio_extension}'))
            chunk_set = AudioChunkSet(chunk_files, temp_directory)
            owned = True

            return chunk_set

        finally:
            if not owned:
                shutil.rmtree(temp_directory, ignore_errors=True)
