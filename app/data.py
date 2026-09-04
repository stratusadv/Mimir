from __future__ import annotations

import io
import os

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from constants import (
    CHUNK_WORKERS_MAX,
    ENVIRONMENT_BOMS,
    ENVIRONMENT_FILE_NAME,
    OUTPUT_MODE_BOTH,
    OUTPUT_MODE_NOTES,
    OUTPUT_MODE_TRANSCRIPT,
    SCRIPT_DIRECTORY,
    SEGMENT_LENGTH_SECONDS,
)


@dataclass(frozen=True)
class ChunkTranscriptions:
    gap_count: int
    texts: list[str]


@dataclass(frozen=True)
class NotesOutput:
    error: Exception | None
    notes_file: Path | None
    search_error: Exception | None


@dataclass(frozen=True)
class TranscriptNotes:
    cleaned_text: str
    summary_text: str


@dataclass(frozen=True)
class TranscriptionOutput:
    gap_count: int
    notes_error: Exception | None
    notes_file: Path | None
    search_error: Exception | None
    transcript_file: Path | None


@dataclass(frozen=True)
class TranscriptionResult:
    gap_count: int
    text: str


@dataclass(frozen=True)
class TranscriptionSettings:
    api_host: str | None
    api_key: str | None
    audio_model: str
    chunk_workers_max: int
    environment_file: Path
    output_mode: str
    result_file: Path | None
    search_query: str
    segment_length_seconds: int
    text_model: str

    @property
    def base_url(self) -> str:
        host = (self.api_host or '').strip().rstrip('/')

        if host.endswith('/v1'):
            return host

        return f'{host}/v1'

    @property
    def configuration_detail(self) -> str:
        if not self.environment_file.is_file():
            return (
                f'No settings file was found. Copy .env.example to .env '
                f'in {self.environment_file.parent}'
            )

        missing_names = self.missing_names
        verb = 'is' if len(missing_names) == 1 else 'are'
        detail = f'{" and ".join(missing_names)} {verb} empty or missing in {self.environment_file}'

        if self.has_unparsable_lines:
            return f'{detail}. Every setting must read NAME=value; some lines have no = sign.'

        return detail

    @staticmethod
    def environment_text(environment_file: Path) -> str:
        content = environment_file.read_bytes()

        for byte_order_mark, encoding in ENVIRONMENT_BOMS:
            if content.startswith(byte_order_mark):
                return content.decode(encoding, errors='replace')

        return content.decode('utf-8', errors='replace')

    @staticmethod
    def environment_value(
            values: dict[str, str | None],
            name: str,
            default: str | None = None,
    ) -> str | None:
        return values.get(name) or os.getenv(name) or default

    @classmethod
    def environment_values(cls, environment_file: Path) -> dict[str, str | None]:
        if not environment_file.is_file():
            return {}

        text_stream = io.StringIO(cls.environment_text(environment_file))

        return dotenv_values(stream=text_stream)

    @classmethod
    def from_environment(cls) -> TranscriptionSettings:
        environment_file = SCRIPT_DIRECTORY / ENVIRONMENT_FILE_NAME
        values = cls.environment_values(environment_file)
        result_path_file = os.getenv('MIMIR_RESULT_FILE')

        return cls(
            api_host=cls.environment_value(values, 'AI_API_HOST'),
            api_key=cls.environment_value(values, 'AI_API_KEY'),
            audio_model=cls.environment_value(values, 'LLM_AUDIO_MODEL', 'stratus.listen'),
            chunk_workers_max=CHUNK_WORKERS_MAX,
            environment_file=environment_file,
            output_mode=os.getenv('MIMIR_OUTPUT_MODE', OUTPUT_MODE_TRANSCRIPT).strip().lower(),
            result_file=Path(result_path_file) if result_path_file else None,
            search_query=os.getenv('MIMIR_SEARCH_QUERY', '').strip(),
            segment_length_seconds=SEGMENT_LENGTH_SECONDS,
            text_model=cls.environment_value(values, 'LLM_TEXT_MODEL', 'stratus.thinking'),
        )

    @property
    def has_unparsable_lines(self) -> bool:
        if not self.environment_file.is_file():
            return False

        lines = self.environment_text(self.environment_file).splitlines()
        content_lines = [line.strip() for line in lines if line.strip()]

        return any('=' not in line for line in content_lines if not line.startswith('#'))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_host and self.api_key)

    @property
    def keeps_transcript(self) -> bool:
        return self.output_mode in (OUTPUT_MODE_BOTH, OUTPUT_MODE_TRANSCRIPT)

    @property
    def missing_names(self) -> list[str]:
        names = []

        if not self.api_host:
            names.append('AI_API_HOST')

        if not self.api_key:
            names.append('AI_API_KEY')

        return names

    @property
    def writes_notes(self) -> bool:
        return self.output_mode in (OUTPUT_MODE_BOTH, OUTPUT_MODE_NOTES)
