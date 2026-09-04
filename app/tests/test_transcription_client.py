from __future__ import annotations

import pytest

import transcription_client

from pathlib import Path
from typing_extensions import Callable

from constants import CHUNK_ATTEMPTS_MAX
from data import TranscriptionSettings
from errors import TranscriptionError
from transcription_client import TranscriptionClient

from .doubles import FakeOpenAI, FakeTranscription


@pytest.fixture(autouse=True)
def openai_faked(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeOpenAI.reset()

    monkeypatch.setattr(transcription_client, 'OpenAI', FakeOpenAI)
    monkeypatch.setattr(transcription_client, 'sleep', lambda seconds: None)


def client_built(settings: TranscriptionSettings, responder: Callable[[str], str | None]) -> TranscriptionClient:
    client = TranscriptionClient(settings)
    client.client.audio.transcriptions.responder = responder

    return client


def test_client_is_built_from_the_settings(settings: TranscriptionSettings) -> None:
    client = TranscriptionClient(settings)

    assert client.client.api_key == 'test-key'
    assert client.client.base_url == 'https://service.test/v1'


def test_request_chunk_transcription_raises_on_an_api_error_payload(
        settings: TranscriptionSettings,
        tmp_path: Path,
) -> None:
    chunk_file = tmp_path / 'chunk_000.mp3'
    chunk_file.write_bytes(b'audio')
    client = TranscriptionClient(settings)
    error_payload = {'message': 'model overloaded'}

    client.client.audio.transcriptions.create = lambda **keywords: FakeTranscription('', error_payload)

    with pytest.raises(TranscriptionError) as error:
        _ = client.request_chunk_transcription(chunk_file)

    assert 'model overloaded' in str(error.value)


def test_request_chunk_transcription_returns_empty_text_for_none(
        settings: TranscriptionSettings,
        tmp_path: Path,
) -> None:
    chunk_file = tmp_path / 'chunk_000.mp3'
    chunk_file.write_bytes(b'audio')
    client = client_built(settings, lambda name: None)

    assert client.request_chunk_transcription(chunk_file) == ''


def test_request_chunk_transcription_sends_the_audio_model(
        settings: TranscriptionSettings,
        tmp_path: Path,
) -> None:
    chunk_file = tmp_path / 'chunk_000.mp3'
    chunk_file.write_bytes(b'audio')
    client = client_built(settings, lambda name: 'spoken words')

    text = client.request_chunk_transcription(chunk_file)
    call = client.client.audio.transcriptions.calls[0]

    assert text == 'spoken words'
    assert call['model'] == 'stratus.listen'
    assert call['file'].name == 'chunk_000.mp3'


def test_transcribe_chunk_raises_after_every_attempt_fails(
        settings: TranscriptionSettings,
        tmp_path: Path,
) -> None:
    chunk_file = tmp_path / 'chunk_000.mp3'
    chunk_file.write_bytes(b'audio')
    attempts: list[int] = []

    def responder(name: str) -> str:
        attempts.append(1)
        message = 'service unavailable'

        raise RuntimeError(message)

    client = client_built(settings, responder)

    with pytest.raises(TranscriptionError) as error:
        _ = client.transcribe_chunk(chunk_file)

    assert len(attempts) == CHUNK_ATTEMPTS_MAX
    assert 'service unavailable' in str(error.value)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_transcribe_chunk_retries_until_it_succeeds(
        settings: TranscriptionSettings,
        tmp_path: Path,
) -> None:
    chunk_file = tmp_path / 'chunk_000.mp3'
    chunk_file.write_bytes(b'audio')
    attempts: list[int] = []

    def responder(name: str) -> str:
        attempts.append(1)

        if len(attempts) < 3:
            message = 'temporary failure'

            raise RuntimeError(message)

        return 'recovered text'

    client = client_built(settings, responder)

    assert client.transcribe_chunk(chunk_file) == 'recovered text'
    assert len(attempts) == 3
