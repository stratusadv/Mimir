from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from constants import (
    CHUNK_WORKERS_MAX,
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
    output_mode: str
    result_file: Path | None
    search_query: str
    segment_length_seconds: int
    text_model: str

    @property
    def base_url(self) -> str:
        return f'{self.api_host}/v1'

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
            search_query=os.getenv('MIMIR_SEARCH_QUERY', '').strip(),
            segment_length_seconds=SEGMENT_LENGTH_SECONDS,
            text_model=os.getenv('LLM_TEXT_MODEL', 'stratus.thinking'),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_host and self.api_key)

    @property
    def keeps_transcript(self) -> bool:
        return self.output_mode in (OUTPUT_MODE_BOTH, OUTPUT_MODE_TRANSCRIPT)

    @property
    def writes_notes(self) -> bool:
        return self.output_mode in (OUTPUT_MODE_BOTH, OUTPUT_MODE_NOTES)
