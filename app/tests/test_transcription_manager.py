from __future__ import annotations

import sys

import pytest

import transcript_polisher
import transcription_client
import transcription_manager

from pathlib import Path
from typing_extensions import Callable

from data import TranscriptionOutput, TranscriptionSettings
from errors import TranscriptionError
from transcription_manager import TranscriptionManager

from .doubles import FakeOpenAI, SilentConsole


class StubTranscriber:
    def __init__(self, output: TranscriptionOutput | None = None, error: Exception | None = None) -> None:
        self.error = error
        self.output = output
        self.seen: list[str] = []

    def transcribe_to_file(self, audio_file: Path) -> TranscriptionOutput:
        self.seen.append(audio_file.name)

        if self.error:
            raise self.error

        return self.output


@pytest.fixture(autouse=True)
def openai_faked(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeOpenAI.reset()

    monkeypatch.setattr(transcript_polisher, 'OpenAI', FakeOpenAI)
    monkeypatch.setattr(transcription_client, 'OpenAI', FakeOpenAI)


def output_built(
        tmp_path: Path,
        gap_count: int = 0,
        notes_error: Exception | None = None,
        notes_file: Path | None = None,
        search_error: Exception | None = None,
        transcript_file: Path | None = None,
) -> TranscriptionOutput:
    return TranscriptionOutput(
        gap_count=gap_count,
        notes_error=notes_error,
        notes_file=notes_file,
        search_error=search_error,
        transcript_file=transcript_file if transcript_file else tmp_path / 'meeting_transcript.txt',
    )


def test_build_transcriber_attaches_a_polisher_for_notes_modes(
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    for output_mode in ('both', 'notes'):
        manager = TranscriptionManager(settings_factory(output_mode=output_mode), SilentConsole())
        transcriber = manager.build_transcriber()

        assert transcriber.polisher is not None


def test_build_transcriber_carries_the_settings_through(
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    settings = settings_factory(
        chunk_workers_max=7,
        output_mode='both',
        search_query='budget',
        segment_length_seconds=45,
    )

    transcriber = TranscriptionManager(settings, SilentConsole()).build_transcriber()

    assert transcriber.chunker.segment_length_seconds == 45
    assert transcriber.keep_transcript
    assert transcriber.search_query == 'budget'
    assert transcriber.workers_max == 7


def test_build_transcriber_omits_the_polisher_for_transcript_mode(
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    manager = TranscriptionManager(settings_factory(output_mode='transcript'), SilentConsole())

    assert manager.build_transcriber().polisher is None


def test_collect_audio_files_globs_the_working_directory(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    (tmp_path / 'one.mp3').write_bytes(b'audio')
    (tmp_path / 'two.wav').write_bytes(b'audio')
    (tmp_path / 'notes.txt').write_text('body', encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['audio_transcription.py'])

    names = sorted(file.name for file in TranscriptionManager.collect_audio_files())

    assert names == ['one.mp3', 'two.wav']


def test_collect_audio_files_reads_the_list_file(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    list_file = tmp_path / 'queue.txt'
    lines = f'{tmp_path / "one.mp3"}\n\n  {tmp_path / "two.m4a"}  \n'
    list_file.write_text(lines, encoding='utf-8')

    monkeypatch.setattr(sys, 'argv', ['audio_transcription.py', str(list_file)])

    audio_files = TranscriptionManager.collect_audio_files()

    assert [file.name for file in audio_files] == ['one.mp3', 'two.m4a']


def test_process_counts_a_failure(
        settings_factory: Callable[..., TranscriptionSettings],
        tmp_path: Path,
) -> None:
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(), console)
    transcriber = StubTranscriber(error=TranscriptionError('ffmpeg was not found.'))

    manager.process(transcriber, tmp_path / 'meeting.mp3')

    assert manager.fail_count == 1
    assert manager.success_count == 0
    assert console.events_named('failure')[0][2] == 'ffmpeg was not found.'


def test_process_records_both_output_files(
        settings_factory: Callable[..., TranscriptionSettings],
        tmp_path: Path,
) -> None:
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(output_mode='both'), console)
    output = output_built(tmp_path, notes_file=tmp_path / 'meeting_notes.txt')

    manager.process(StubTranscriber(output=output), tmp_path / 'meeting.mp3')

    expected = ['meeting_transcript.txt', 'meeting_notes.txt']

    assert manager.success_count == 1
    assert [file.name for file in manager.output_files] == expected
    assert console.events_named('notes')[0][1] == 'meeting_notes.txt'


def test_process_reports_gaps(
        settings_factory: Callable[..., TranscriptionSettings],
        tmp_path: Path,
) -> None:
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(segment_length_seconds=30), console)
    transcriber = StubTranscriber(output=output_built(tmp_path, gap_count=3))

    manager.process(transcriber, tmp_path / 'meeting.mp3')

    assert manager.gap_count == 3
    assert manager.gap_file_count == 1
    assert console.events_named('gaps')[0] == ('gaps', 3, 90)


def test_process_reports_notes_and_search_errors(
        settings_factory: Callable[..., TranscriptionSettings],
        tmp_path: Path,
) -> None:
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(), console)

    output = output_built(
        tmp_path,
        notes_error=RuntimeError('notes failed'),
        search_error=RuntimeError('search failed'),
    )

    manager.process(StubTranscriber(output=output), tmp_path / 'meeting.mp3')

    assert console.events_named('notes_failure')[0][1] == 'notes failed'
    assert console.events_named('search_failure')[0][1] == 'search failed'


def test_report_result_file_writes_every_output_path(
        settings_factory: Callable[..., TranscriptionSettings],
        tmp_path: Path,
) -> None:
    result_file = tmp_path / 'result.txt'
    manager = TranscriptionManager(settings_factory(result_file=result_file), SilentConsole())
    manager.output_files = [tmp_path / 'one_transcript.txt']

    manager.report_result_file()

    assert result_file.read_text(encoding='utf-8') == str(tmp_path / 'one_transcript.txt')


def test_run_rejects_an_unknown_output_mode(
        monkeypatch: pytest.MonkeyPatch,
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    monkeypatch.setattr(sys, 'argv', ['audio_transcription.py'])
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(output_mode='summary'), console)

    assert manager.run() == 1
    assert console.events_named('error')[0][1] == 'Unknown output mode: summary'


def test_run_reports_missing_settings(
        monkeypatch: pytest.MonkeyPatch,
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    monkeypatch.setattr(sys, 'argv', ['audio_transcription.py'])
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(api_host=None), console)

    assert manager.run() == 1
    assert console.events_named('error')[0][1] == 'No API settings were found.'
    assert str(transcription_manager.SCRIPT_DIRECTORY) in console.events_named('error')[0][2]


def test_run_warns_when_there_is_nothing_to_transcribe(
        monkeypatch: pytest.MonkeyPatch,
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    monkeypatch.setattr(sys, 'argv', ['audio_transcription.py'])
    console = SilentConsole()
    manager = TranscriptionManager(settings_factory(), console)

    assert manager.run() == 0
    assert console.events_named('warning')[0][1] == 'No audio files to transcribe.'
