from __future__ import annotations

import logging

from concurrent.futures import as_completed
from time import sleep

from openai import OpenAI

from constants import (
    POLISH_ATTEMPTS_MAX,
    POLISH_CHARACTERS_MAX,
    POLISH_RETRY_BACKOFF_SECONDS,
    POLISH_TIMEOUT_SECONDS,
    POLISH_WORKERS_MAX,
)
from data import TranscriptNotes, TranscriptionSettings
from errors import TranscriptionError
from prompts import CLEANUP_INSTRUCTIONS, SECTION_INSTRUCTIONS, SUMMARY_INSTRUCTIONS
from thread_pool import ThreadPool


log = logging.getLogger('mimir')


class TranscriptPolisher:
    def __init__(self, settings: TranscriptionSettings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    @staticmethod
    def chunk_lines(lines: list[str], characters_max: int) -> list[str]:
        chunks: list[str] = []
        current_lines: list[str] = []
        current_length = 0

        for line in lines:
            if current_lines and current_length + len(line) > characters_max:
                chunks.append('\n'.join(current_lines))
                current_lines = []
                current_length = 0

            current_lines.append(line)
            current_length += len(line) + 1

        if current_lines:
            chunks.append('\n'.join(current_lines))

        return chunks

    def complete(self, instructions: str, content: str) -> str:
        last_error: Exception | None = None

        for attempt in range(POLISH_ATTEMPTS_MAX):
            if attempt:
                sleep(POLISH_RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1))

            try:
                completion_text = self.request_completion(instructions, content)

            except Exception as error:
                last_error = error

                log.warning(
                    'text model attempt failed  attempt=%s/%s  error=%s',
                    attempt + 1,
                    POLISH_ATTEMPTS_MAX,
                    last_error,
                )

            else:
                return completion_text

        message = f'the text model failed after {POLISH_ATTEMPTS_MAX} attempts. {last_error}'
        raise TranscriptionError(message) from last_error

    def complete_many(self, instructions: str, contents: list[str]) -> list[str]:
        completion_texts: list[str] = [''] * len(contents)

        with ThreadPool(POLISH_WORKERS_MAX) as thread_executor:
            future_to_index = {
                thread_executor.submit(self.complete, instructions, content): index
                for index, content in enumerate(contents)
            }

            for future in as_completed(future_to_index):
                index: int = future_to_index[future]
                completion_texts[index] = future.result().strip()

        return completion_texts

    def polish(self, transcript_text: str) -> TranscriptNotes:
        chunks = self.chunk_lines(transcript_text.splitlines(), POLISH_CHARACTERS_MAX)
        cleaned_chunks = self.complete_many(CLEANUP_INSTRUCTIONS, chunks)
        cleaned_text = '\n\n'.join(text for text in cleaned_chunks if text)

        if not cleaned_text:
            message = 'the text model returned no cleaned transcript.'
            raise TranscriptionError(message)

        summary_text = self.summarize(cleaned_chunks)

        if not summary_text:
            message = 'the text model returned no summary.'
            raise TranscriptionError(message)

        return TranscriptNotes(cleaned_text=cleaned_text, summary_text=summary_text)

    def request_completion(self, instructions: str, content: str) -> str:
        system_message = {'role': 'system', 'content': instructions}
        user_message = {'role': 'user', 'content': content}
        messages = [system_message, user_message]

        completion = self.client.chat.completions.create(
            model=self.settings.text_model,
            messages=messages,
            timeout=POLISH_TIMEOUT_SECONDS,
        )

        message_content = completion.choices[0].message.content

        return message_content if message_content else ''

    def summarize(self, cleaned_chunks: list[str]) -> str:
        if len(cleaned_chunks) == 1:
            return self.complete(SUMMARY_INSTRUCTIONS, cleaned_chunks[0]).strip()

        section_notes = self.complete_many(SECTION_INSTRUCTIONS, cleaned_chunks)
        joined_notes = '\n'.join(text for text in section_notes if text)

        return self.complete(SUMMARY_INSTRUCTIONS, joined_notes).strip()
