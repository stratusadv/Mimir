from __future__ import annotations

import builtins

import pytest

from pathlib import Path
from typing_extensions import Callable

from console import Console
from constants import LOG_PATH


def answers_queued(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> list[str]:
    remaining = list(answers)

    def read(prompt: str = '') -> str:
        if not remaining:
            raise EOFError

        return remaining.pop(0)

    monkeypatch.setattr(builtins, 'input', read)

    return remaining


def test_error_prints_only_the_message_without_detail(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
) -> None:
    Console().error('No search request was given.')

    assert ansi_stripped(capsys.readouterr().out).strip() == '[ERROR] No search request was given.'


def test_error_prints_the_message_and_detail(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
) -> None:
    Console().error('No API settings were found.', 'Expected a .env file beside the script: C:\\Mimir\\app')

    text = ansi_stripped(capsys.readouterr().out)

    assert '[ERROR] No API settings were found.' in text
    assert 'Expected a .env file beside the script: C:\\Mimir\\app' in text


def test_failure_prints_the_file_and_error(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
        tmp_path: Path,
) -> None:
    Console().failure(tmp_path / 'meeting.mp3', RuntimeError('ffmpeg was not found.'))

    text = ansi_stripped(capsys.readouterr().out)

    assert '[FAIL] meeting.mp3' in text
    assert 'ffmpeg was not found.' in text


def test_gaps_uses_singular_and_plural_labels(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
) -> None:
    console = Console()
    console.gaps(1, 30)
    console.gaps(2, 60)

    lines = ansi_stripped(capsys.readouterr().out).splitlines()

    assert '1 piece could not be transcribed' in lines[0]
    assert '2 pieces could not be transcribed' in lines[1]


def test_progress_reports_the_percentage(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
        tmp_path: Path,
) -> None:
    Console().progress(tmp_path / 'meeting.mp3', 1, 4)

    text = ansi_stripped(capsys.readouterr().out)

    assert '[  25% ] meeting.mp3' in text
    assert '(1 of 4 pieces)' in text


def test_search_save_ask_gives_up_after_ten_invalid_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    remaining = answers_queued(monkeypatch, ['maybe'] * 12)

    assert Console().search_save_ask() is False
    assert len(remaining) == 2


def test_search_save_ask_reads_yes_and_no(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = answers_queued(monkeypatch, [' Y '])

    assert Console().search_save_ask() is True

    _ = answers_queued(monkeypatch, ['no'])

    assert Console().search_save_ask() is False


def test_search_save_ask_retries_after_an_invalid_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = answers_queued(monkeypatch, ['maybe', 'yes'])

    assert Console().search_save_ask() is True


def test_search_save_ask_returns_false_on_end_of_input(monkeypatch: pytest.MonkeyPatch) -> None:
    _ = answers_queued(monkeypatch, [])

    assert Console().search_save_ask() is False


def test_search_start_truncates_a_long_query(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
        tmp_path: Path,
) -> None:
    Console().search_start(tmp_path / 'report.txt', 'x' * 100)

    text = ansi_stripped(capsys.readouterr().out)

    assert text.endswith(f'{"x" * 57}...')


def test_summary_points_at_the_log_when_something_went_wrong(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
) -> None:
    Console().summary(2, 1, 1, 3)

    text = ansi_stripped(capsys.readouterr().out)

    assert '2 transcribed' in text
    assert '1 failed' in text
    assert '3 audio pieces missing across 1 file' in text
    assert str(LOG_PATH) in text


def test_summary_stays_quiet_when_nothing_went_wrong(
        ansi_stripped: Callable[[str], str],
        capsys: pytest.CaptureFixture,
) -> None:
    Console().summary(2, 0, 0, 0, success_label='searched')

    text = ansi_stripped(capsys.readouterr().out)

    assert '2 searched' in text
    assert str(LOG_PATH) not in text
