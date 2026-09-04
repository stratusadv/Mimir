from __future__ import annotations

import shutil
import subprocess

import pytest

import audio_chunker

from pathlib import Path

from audio_chunker import AudioChunker, AudioChunkSet
from constants import SUPPORTED_AUDIO_EXTENSIONS
from errors import TranscriptionError


def test_audio_extension_accepts_every_supported_extension(tmp_path: Path) -> None:
    for extension in SUPPORTED_AUDIO_EXTENSIONS:
        audio_file = tmp_path / f'meeting.{extension}'

        assert AudioChunker.audio_extension(audio_file) == extension


def test_audio_extension_is_case_insensitive(tmp_path: Path) -> None:
    assert AudioChunker.audio_extension(tmp_path / 'meeting.MP3') == 'mp3'


def test_audio_extension_rejects_unsupported_extension(tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError) as error:
        _ = AudioChunker.audio_extension(tmp_path / 'notes.pdf')

    assert 'notes.pdf' in str(error.value)
    assert 'mp3' in str(error.value)


def test_chunk_removes_the_temporary_directory_when_ffmpeg_fails(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    created: list[Path] = []

    def run_failing(command: list[str], **keywords) -> subprocess.CompletedProcess:
        created.append(Path(command[-1]).parent)

        raise subprocess.CalledProcessError(1, command, stderr='header\nInvalid data found\n')

    monkeypatch.setattr(audio_chunker.subprocess, 'run', run_failing)

    with pytest.raises(TranscriptionError) as error:
        _ = AudioChunker().chunk(tmp_path / 'meeting.mp3')

    assert 'Invalid data found' in str(error.value)
    assert not created[0].exists()


def test_chunk_reports_a_readable_message_when_ffmpeg_is_absent(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    def run_absent(command: list[str], **keywords) -> subprocess.CompletedProcess:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(audio_chunker.subprocess, 'run', run_absent)

    with pytest.raises(TranscriptionError) as error:
        _ = AudioChunker().chunk(tmp_path / 'meeting.mp3')

    assert 'ffmpeg was not found' in str(error.value)


def test_chunk_returns_sorted_chunk_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def run_writing(command: list[str], **keywords) -> subprocess.CompletedProcess:
        output_directory = Path(command[-1]).parent

        for index in (2, 0, 1):
            (output_directory / f'chunk_{index:03d}.mp3').write_bytes(b'audio')

        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(audio_chunker.subprocess, 'run', run_writing)

    chunk_set = AudioChunker().chunk(tmp_path / 'meeting.mp3')

    with chunk_set:
        names = [chunk_file.name for chunk_file in chunk_set.chunk_files]

        assert len(chunk_set) == 3
        assert names == ['chunk_000.mp3', 'chunk_001.mp3', 'chunk_002.mp3']

    assert not chunk_set.temp_directory.exists()


def test_chunk_set_discard_is_safe_to_repeat(tmp_path: Path) -> None:
    temp_directory = tmp_path / 'chunks'
    temp_directory.mkdir()

    chunk_set = AudioChunkSet([], temp_directory)
    chunk_set.discard()
    chunk_set.discard()

    assert not temp_directory.exists()


def test_chunk_uses_the_configured_segment_length(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorded: list[list[str]] = []

    def run_recording(command: list[str], **keywords) -> subprocess.CompletedProcess:
        recorded.append(command)

        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(audio_chunker.subprocess, 'run', run_recording)

    chunk_set = AudioChunker(segment_length_seconds=45).chunk(tmp_path / 'meeting.wav')
    chunk_set.discard()

    command = recorded[0]

    assert command[0] == 'ffmpeg'
    assert command[command.index('-segment_time') + 1] == '45'
    assert command[-1].endswith('chunk_%03d.wav')


@pytest.mark.ffmpeg
def test_chunk_splits_a_real_audio_file(audio_fixture_directory: Path) -> None:
    if shutil.which('ffmpeg') is None:
        pytest.skip('ffmpeg is not on PATH')

    audio_file = audio_fixture_directory / 'sample_two_speakers.mp3'

    if not audio_file.is_file():
        pytest.skip(f'missing fixture: {audio_file}')

    with AudioChunker(segment_length_seconds=5).chunk(audio_file) as chunk_set:
        assert len(chunk_set) > 0
        assert all(chunk_file.stat().st_size > 0 for chunk_file in chunk_set.chunk_files)
