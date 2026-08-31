from __future__ import annotations

import logging
import sys

from pathlib import Path
from time import perf_counter

from audio_chunker import AudioChunker
from audio_file_transcriber import AudioFileTranscriber
from console import Console
from constants import OUTPUT_MODES, SCRIPT_DIRECTORY, SUPPORTED_AUDIO_EXTENSIONS
from data import TranscriptionSettings
from transcript_polisher import TranscriptPolisher
from transcription_client import TranscriptionClient


log = logging.getLogger('mimir')


class TranscriptionManager:
    def __init__(self, settings: TranscriptionSettings, console: Console | None = None) -> None:
        self.settings = settings
        self.console = console if console else Console()
        self.fail_count = 0
        self.gap_count = 0
        self.gap_file_count = 0
        self.output_files: list[Path] = []
        self.success_count = 0

    def build_transcriber(self) -> AudioFileTranscriber:
        polisher = TranscriptPolisher(self.settings) if self.settings.writes_notes else None

        return AudioFileTranscriber(
            chunker=AudioChunker(self.settings.segment_length_seconds),
            client=TranscriptionClient(self.settings),
            console=self.console,
            keep_transcript=self.settings.keeps_transcript,
            polisher=polisher,
            search_query=self.settings.search_query,
            workers_max=self.settings.chunk_workers_max,
        )

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

            if output.search_error:
                self.console.search_failure(output.search_error)

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
