from __future__ import annotations

import io
import logging
import random

from pathlib import Path
from time import sleep

from openai import OpenAI

from constants import (
    CHUNK_ATTEMPTS_MAX,
    CHUNK_RETRY_BACKOFF_SECONDS,
    CHUNK_RETRY_JITTER_SECONDS,
)
from data import TranscriptionSettings
from errors import TranscriptionError


log = logging.getLogger('mimir')


class TranscriptionClient:
    def __init__(self, settings: TranscriptionSettings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    def request_chunk_transcription(self, audio_chunk_file: Path) -> str:
        audio_buffer = io.BytesIO(audio_chunk_file.read_bytes())
        audio_buffer.name = audio_chunk_file.name

        transcription = self.client.audio.transcriptions.create(
            model=self.settings.audio_model,
            file=audio_buffer,
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
