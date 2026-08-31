from __future__ import annotations

import logging
import re

from concurrent.futures import as_completed
from pathlib import Path

from audio_chunker import AudioChunker, AudioChunkSet
from console import Console
from constants import CHUNK_WORKERS_MAX, OUTPUT_ATTEMPTS_MAX
from data import (
    ChunkTranscriptions,
    NotesOutput,
    TranscriptNotes,
    TranscriptionOutput,
    TranscriptionResult,
)
from document_searcher import DocumentSearcher
from errors import TranscriptionError
from thread_pool import ThreadPool
from transcript_polisher import TranscriptPolisher
from transcription_client import TranscriptionClient


log = logging.getLogger('mimir')


class AudioFileTranscriber:
    def __init__(
            self,
            chunker: AudioChunker,
            client: TranscriptionClient,
            console: Console,
            keep_transcript: bool = True,
            polisher: TranscriptPolisher | None = None,
            search_query: str = '',
            workers_max: int = CHUNK_WORKERS_MAX,
    ) -> None:
        self.chunker = chunker
        self.client = client
        self.console = console
        self.keep_transcript = keep_transcript
        self.polisher = polisher
        self.search_query = search_query
        self.workers_max = workers_max

    @staticmethod
    def format_notes(
            audio_file: Path,
            notes: TranscriptNotes,
            *,
            search_query: str = '',
            search_text: str = '',
    ) -> str:
        sections = [
            'MIMIR NOTES',
            audio_file.name,
            '',
            'AI wrote these notes from the transcript. Check them before you rely on them.',
            '',
            notes.summary_text,
        ]

        if search_text:
            highlight_sections = [
                '',
                'SEARCH HIGHLIGHTS',
                '',
                f'Query: {search_query}',
                '',
                search_text,
            ]

            sections.extend(highlight_sections)

        transcript_sections = [
            '',
            'CLEANED TRANSCRIPT',
            '',
            notes.cleaned_text,
            '',
        ]

        sections.extend(transcript_sections)

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

        with ThreadPool(self.workers_max) as thread_executor:
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
            search_error=notes_output.search_error,
            transcript_file=kept_transcript_file,
        )

    def write_notes(self, audio_file: Path, transcript_text: str) -> NotesOutput:
        if self.polisher is None:
            return NotesOutput(error=None, notes_file=None, search_error=None)

        self.console.notes_start(audio_file)

        try:
            notes = self.polisher.polish(transcript_text)

        except Exception as error:
            log.exception('notes failed  file=%s', audio_file.name)

            return NotesOutput(error=error, notes_file=None, search_error=None)

        else:
            search_text, search_error = self.write_notes_search(audio_file, notes.cleaned_text)
            notes_file = self.free_output_file(audio_file, 'notes')

            notes_text = self.format_notes(
                audio_file,
                notes,
                search_query=self.search_query,
                search_text=search_text,
            )

            notes_file.write_text(notes_text, encoding='utf-8')

            return NotesOutput(error=None, notes_file=notes_file, search_error=search_error)

    def write_notes_search(self, audio_file: Path, transcript_text: str) -> tuple[str, Exception | None]:
        if not self.search_query:
            return '', None

        polisher = self.polisher

        if polisher is None:
            return '', None

        self.console.search_start(audio_file, self.search_query)

        try:
            findings = DocumentSearcher(polisher).search(transcript_text, self.search_query)

        except Exception as error:
            log.exception('search failed  file=%s', audio_file.name)

            return '', error

        else:
            return findings, None
