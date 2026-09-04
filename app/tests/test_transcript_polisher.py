from __future__ import annotations

import pytest

import transcript_polisher

from typing_extensions import Callable

from constants import POLISH_ATTEMPTS_MAX
from data import TranscriptionSettings
from errors import TranscriptionError
from prompts import CLEANUP_INSTRUCTIONS, SECTION_INSTRUCTIONS, SUMMARY_INSTRUCTIONS
from transcript_polisher import TranscriptPolisher

from .doubles import FakeOpenAI


@pytest.fixture(autouse=True)
def openai_faked(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeOpenAI.reset()

    monkeypatch.setattr(transcript_polisher, 'OpenAI', FakeOpenAI)
    monkeypatch.setattr(transcript_polisher, 'sleep', lambda seconds: None)


def polisher_built(
        settings: TranscriptionSettings,
        responder: Callable[[list[dict], str], str | None],
) -> TranscriptPolisher:
    polisher = TranscriptPolisher(settings)
    polisher.client.chat.completions.responder = responder

    return polisher


def test_chunk_lines_keeps_every_line() -> None:
    lines = [f'line {index}' for index in range(50)]
    chunks = TranscriptPolisher.chunk_lines(lines, 30)
    rejoined = '\n'.join(chunks).splitlines()

    assert rejoined == lines


def test_chunk_lines_keeps_one_overlong_line_whole() -> None:
    lines = ['x' * 500]

    assert TranscriptPolisher.chunk_lines(lines, 10) == lines


def test_chunk_lines_returns_nothing_for_no_lines() -> None:
    assert TranscriptPolisher.chunk_lines([], 100) == []


def test_chunk_lines_splits_at_the_character_limit() -> None:
    lines = ['aaaa', 'bbbb', 'cccc']
    chunks = TranscriptPolisher.chunk_lines(lines, 9)

    assert chunks == ['aaaa\nbbbb', 'cccc']


def test_complete_many_keeps_order_and_strips(settings: TranscriptionSettings) -> None:
    def responder(messages: list[dict], model: str) -> str:
        return f'  {messages[1]["content"]} done  '

    polisher = polisher_built(settings, responder)
    contents = ['first', 'second', 'third']
    expected = ['first done', 'second done', 'third done']

    assert polisher.complete_many('instructions', contents) == expected


def test_complete_raises_after_every_attempt_fails(settings: TranscriptionSettings) -> None:
    attempts: list[int] = []

    def responder(messages: list[dict], model: str) -> str:
        attempts.append(1)
        message = 'gateway timeout'

        raise RuntimeError(message)

    polisher = polisher_built(settings, responder)

    with pytest.raises(TranscriptionError) as error:
        _ = polisher.complete('instructions', 'content')

    assert len(attempts) == POLISH_ATTEMPTS_MAX
    assert 'gateway timeout' in str(error.value)


def test_complete_retries_until_it_succeeds(settings: TranscriptionSettings) -> None:
    attempts: list[int] = []

    def responder(messages: list[dict], model: str) -> str:
        attempts.append(1)

        if len(attempts) < 2:
            message = 'temporary failure'

            raise RuntimeError(message)

        return 'recovered'

    polisher = polisher_built(settings, responder)

    assert polisher.complete('instructions', 'content') == 'recovered'
    assert len(attempts) == 2


def test_polish_raises_without_a_cleaned_transcript(settings: TranscriptionSettings) -> None:
    polisher = polisher_built(settings, lambda messages, model: '')

    with pytest.raises(TranscriptionError) as error:
        _ = polisher.polish('one line')

    assert 'no cleaned transcript' in str(error.value)


def test_polish_raises_without_a_summary(settings: TranscriptionSettings) -> None:
    def responder(messages: list[dict], model: str) -> str:
        return 'cleaned body' if messages[0]['content'] == CLEANUP_INSTRUCTIONS else ''

    polisher = polisher_built(settings, responder)

    with pytest.raises(TranscriptionError) as error:
        _ = polisher.polish('one line')

    assert 'no summary' in str(error.value)


def test_polish_returns_cleaned_text_and_summary(settings: TranscriptionSettings) -> None:
    def responder(messages: list[dict], model: str) -> str:
        return 'cleaned body' if messages[0]['content'] == CLEANUP_INSTRUCTIONS else 'summary body'

    polisher = polisher_built(settings, responder)
    notes = polisher.polish('one line')

    assert notes.cleaned_text == 'cleaned body'
    assert notes.summary_text == 'summary body'


def test_request_completion_returns_empty_text_for_none(settings: TranscriptionSettings) -> None:
    polisher = polisher_built(settings, lambda messages, model: None)

    assert polisher.request_completion('instructions', 'content') == ''


def test_request_completion_sends_the_text_model(settings: TranscriptionSettings) -> None:
    polisher = polisher_built(settings, lambda messages, model: 'answer')
    text = polisher.request_completion('instructions', 'content')
    call = polisher.client.chat.completions.calls[0]
    system_message = {'role': 'system', 'content': 'instructions'}
    user_message = {'role': 'user', 'content': 'content'}

    assert text == 'answer'
    assert call['model'] == 'stratus.thinking'
    assert call['messages'][0] == system_message
    assert call['messages'][1] == user_message


def test_summarize_merges_section_notes_for_many_chunks(settings: TranscriptionSettings) -> None:
    seen: list[str] = []

    def responder(messages: list[dict], model: str) -> str:
        seen.append(messages[0]['content'])

        return 'section note' if messages[0]['content'] == SECTION_INSTRUCTIONS else 'final summary'

    polisher = polisher_built(settings, responder)

    assert polisher.summarize(['first', 'second']) == 'final summary'
    assert SECTION_INSTRUCTIONS in seen
    assert SUMMARY_INSTRUCTIONS in seen


def test_summarize_skips_section_notes_for_one_chunk(settings: TranscriptionSettings) -> None:
    seen: list[str] = []

    def responder(messages: list[dict], model: str) -> str:
        seen.append(messages[0]['content'])

        return 'final summary'

    polisher = polisher_built(settings, responder)

    assert polisher.summarize(['only chunk']) == 'final summary'
    assert seen == [SUMMARY_INSTRUCTIONS]
