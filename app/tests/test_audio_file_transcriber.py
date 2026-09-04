from __future__ import annotations

import pytest

import audio_file_transcriber

from pathlib import Path

from audio_file_transcriber import AudioFileTranscriber
from data import TranscriptNotes
from errors import TranscriptionError

from .doubles import FakeAudioChunker, FakePolisher, FakeTranscriptionClient, SilentConsole


def chunk_directory_built(tmp_path: Path, count: int) -> tuple[Path, list[Path]]:
    chunk_directory = tmp_path / 'chunks'
    chunk_directory.mkdir(exist_ok=True)
    chunk_files = []

    for index in range(count):
        chunk_file = chunk_directory / f'chunk_{index:03d}.mp3'
        chunk_file.write_bytes(b'audio')
        chunk_files.append(chunk_file)

    return chunk_directory, chunk_files


def transcriber_built(
        tmp_path: Path,
        chunk_count: int = 3,
        texts: dict[str, str] | None = None,
        failures: set[str] | None = None,
        keep_transcript: bool = True,
        polisher: FakePolisher | None = None,
        search_query: str = '',
) -> tuple[AudioFileTranscriber, SilentConsole, FakeTranscriptionClient]:
    chunk_directory, chunk_files = chunk_directory_built(tmp_path, chunk_count)
    default_texts = {chunk_file.name: f'part {index}.' for index, chunk_file in enumerate(chunk_files)}
    client = FakeTranscriptionClient(texts if texts is not None else default_texts, failures)
    console = SilentConsole()

    transcriber = AudioFileTranscriber(
        chunker=FakeAudioChunker(chunk_files, chunk_directory),
        client=client,
        console=console,
        keep_transcript=keep_transcript,
        polisher=polisher,
        search_query=search_query,
        workers_max=2,
    )

    return transcriber, console, client


def test_format_notes_includes_the_search_block_with_findings(tmp_path: Path) -> None:
    notes = TranscriptNotes(cleaned_text='cleaned body', summary_text='summary body')

    text = AudioFileTranscriber.format_notes(
        tmp_path / 'meeting.mp3',
        notes,
        search_query='budget',
        search_text='budget findings',
    )

    assert 'SEARCH HIGHLIGHTS' in text
    assert 'Query: budget' in text
    assert text.index('budget findings') < text.index('CLEANED TRANSCRIPT')


def test_format_notes_omits_the_search_block_without_findings(tmp_path: Path) -> None:
    notes = TranscriptNotes(cleaned_text='cleaned body', summary_text='summary body')
    text = AudioFileTranscriber.format_notes(tmp_path / 'meeting.mp3', notes)

    assert 'SEARCH HIGHLIGHTS' not in text
    assert 'CLEANED TRANSCRIPT' in text
    assert 'summary body' in text


def test_format_transcription_breaks_lines_on_sentence_ends() -> None:
    text = AudioFileTranscriber.format_transcription('One. Two! Three? Four')

    assert text == 'One.\nTwo!\nThree?\nFour'


def test_format_transcription_leaves_text_without_sentence_ends_alone() -> None:
    assert AudioFileTranscriber.format_transcription('no sentence end here') == 'no sentence end here'


def test_free_output_file_adds_a_suffix_when_the_name_is_taken(tmp_path: Path) -> None:
    audio_file = tmp_path / 'Team Meeting.mp3'
    (tmp_path / 'team_meeting_transcript.txt').write_text('taken', encoding='utf-8')
    (tmp_path / 'team_meeting_transcript (1).txt').write_text('taken', encoding='utf-8')

    output_file = AudioFileTranscriber.free_output_file(audio_file, 'transcript')

    assert output_file.name == 'team_meeting_transcript (2).txt'


def test_free_output_file_normalises_the_stem(tmp_path: Path) -> None:
    output_file = AudioFileTranscriber.free_output_file(tmp_path / 'Team Meeting.MP3', 'notes')

    assert output_file.name == 'team_meeting_notes.txt'
    assert output_file.parent == tmp_path


def test_free_output_file_raises_after_too_many_attempts(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    monkeypatch.setattr(audio_file_transcriber, 'OUTPUT_ATTEMPTS_MAX', 1)

    (tmp_path / 'meeting_transcript.txt').write_text('taken', encoding='utf-8')
    (tmp_path / 'meeting_transcript (1).txt').write_text('taken', encoding='utf-8')

    with pytest.raises(TranscriptionError) as error:
        _ = AudioFileTranscriber.free_output_file(tmp_path / 'meeting.mp3', 'transcript')

    assert 'too many existing files' in str(error.value)


def test_inaudible_marker_uses_the_chunk_length(tmp_path: Path) -> None:
    transcriber, _, _ = transcriber_built(tmp_path)

    assert transcriber.inaudible_marker(0) == '[inaudible 00:00-00:30]'
    assert transcriber.inaudible_marker(2) == '[inaudible 01:00-01:30]'


def test_timestamp_label_switches_to_hours() -> None:
    assert AudioFileTranscriber.timestamp_label(0) == '00:00'
    assert AudioFileTranscriber.timestamp_label(90) == '01:30'
    assert AudioFileTranscriber.timestamp_label(3661) == '1:01:01'


def test_transcribe_chunks_keeps_order_and_marks_gaps(tmp_path: Path) -> None:
    failures = {'chunk_001.mp3'}
    transcriber, console, _ = transcriber_built(tmp_path, chunk_count=3, failures=failures)
    chunk_set = transcriber.chunker.chunk(tmp_path / 'meeting.mp3')

    chunk_transcriptions = transcriber.transcribe_chunks(tmp_path / 'meeting.mp3', chunk_set)

    assert chunk_transcriptions.gap_count == 1
    assert chunk_transcriptions.texts[0] == 'part 0.'
    assert chunk_transcriptions.texts[1] == '[inaudible 00:30-01:00]'
    assert chunk_transcriptions.texts[2] == 'part 2.'
    assert len(console.events_named('progress')) == 3


def test_transcribe_raises_when_every_chunk_fails(tmp_path: Path) -> None:
    failures = {'chunk_000.mp3', 'chunk_001.mp3'}
    transcriber, _, _ = transcriber_built(tmp_path, chunk_count=2, failures=failures)

    with pytest.raises(TranscriptionError) as error:
        _ = transcriber.transcribe(tmp_path / 'meeting.mp3')

    assert 'every piece of audio failed' in str(error.value)


def test_transcribe_raises_when_no_chunks_are_produced(tmp_path: Path) -> None:
    transcriber, _, _ = transcriber_built(tmp_path, chunk_count=0)

    with pytest.raises(TranscriptionError) as error:
        _ = transcriber.transcribe(tmp_path / 'meeting.mp3')

    assert 'no audio could be read' in str(error.value)


def test_transcribe_raises_when_the_service_returns_no_words(tmp_path: Path) -> None:
    texts = {'chunk_000.mp3': '', 'chunk_001.mp3': ''}
    transcriber, _, _ = transcriber_built(tmp_path, chunk_count=2, texts=texts)

    with pytest.raises(TranscriptionError) as error:
        _ = transcriber.transcribe(tmp_path / 'meeting.mp3')

    assert 'no words' in str(error.value)


def test_transcribe_to_file_keeps_the_transcript_without_a_polisher(tmp_path: Path) -> None:
    audio_file = tmp_path / 'meeting.mp3'
    audio_file.write_bytes(b'audio')
    transcriber, _, _ = transcriber_built(tmp_path, chunk_count=2)

    output = transcriber.transcribe_to_file(audio_file)

    assert output.notes_file is None
    assert output.transcript_file is not None
    assert output.transcript_file.read_text(encoding='utf-8') == 'part 0.\npart 1.'


def test_transcribe_to_file_records_a_notes_failure(tmp_path: Path) -> None:
    audio_file = tmp_path / 'meeting.mp3'
    audio_file.write_bytes(b'audio')
    polisher = FakePolisher(error=RuntimeError('text model down'))
    transcriber, _, _ = transcriber_built(tmp_path, chunk_count=1, polisher=polisher)

    output = transcriber.transcribe_to_file(audio_file)

    assert output.notes_file is None
    assert str(output.notes_error) == 'text model down'
    assert output.transcript_file is not None


def test_transcribe_to_file_removes_the_transcript_in_notes_only_mode(tmp_path: Path) -> None:
    audio_file = tmp_path / 'meeting.mp3'
    audio_file.write_bytes(b'audio')

    transcriber, _, _ = transcriber_built(
        tmp_path,
        chunk_count=1,
        keep_transcript=False,
        polisher=FakePolisher(),
    )

    output = transcriber.transcribe_to_file(audio_file)

    assert output.transcript_file is None
    assert output.notes_file is not None
    assert not (tmp_path / 'meeting_transcript.txt').exists()


def test_transcribe_to_file_writes_search_highlights_into_the_notes(tmp_path: Path) -> None:
    audio_file = tmp_path / 'meeting.mp3'
    audio_file.write_bytes(b'audio')
    polisher = FakePolisher(findings_text='the budget was raised')

    transcriber, _, _ = transcriber_built(
        tmp_path,
        chunk_count=1,
        polisher=polisher,
        search_query='budget',
    )

    output = transcriber.transcribe_to_file(audio_file)
    notes_text = output.notes_file.read_text(encoding='utf-8')

    assert output.search_error is None
    assert 'SEARCH HIGHLIGHTS' in notes_text
    assert 'the budget was raised' in notes_text


def test_write_notes_search_is_skipped_without_a_query(tmp_path: Path) -> None:
    transcriber, console, _ = transcriber_built(tmp_path, chunk_count=1, polisher=FakePolisher())

    search_text, search_error = transcriber.write_notes_search(tmp_path / 'meeting.mp3', 'body')

    assert search_text == ''
    assert search_error is None
    assert 'search_start' not in console.event_names()
