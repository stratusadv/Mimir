from __future__ import annotations

from pathlib import Path

from constants import (
    CHUNK_ATTEMPTS_MAX,
    CHUNK_WORKERS_MAX,
    LOG_PATH,
    OUTPUT_ATTEMPTS_MAX,
    OUTPUT_MODE_BOTH,
    OUTPUT_MODE_NOTES,
    OUTPUT_MODE_TRANSCRIPT,
    OUTPUT_MODES,
    POLISH_ATTEMPTS_MAX,
    POLISH_CHARACTERS_MAX,
    POLISH_WORKERS_MAX,
    SCRIPT_DIRECTORY,
    SEARCH_CHUNKS_MAX,
    SEARCH_QUERY_CHARACTERS_MAX,
    SEGMENT_LENGTH_SECONDS,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)


def test_attempt_and_worker_limits_are_positive() -> None:
    limits = (
        CHUNK_ATTEMPTS_MAX,
        CHUNK_WORKERS_MAX,
        OUTPUT_ATTEMPTS_MAX,
        POLISH_ATTEMPTS_MAX,
        POLISH_CHARACTERS_MAX,
        POLISH_WORKERS_MAX,
        SEARCH_CHUNKS_MAX,
        SEARCH_QUERY_CHARACTERS_MAX,
        SEGMENT_LENGTH_SECONDS,
    )

    assert all(limit > 0 for limit in limits)


def test_log_path_sits_beside_the_app_directory() -> None:
    assert LOG_PATH == SCRIPT_DIRECTORY.parent / 'mimir.log'


def test_output_modes_hold_exactly_the_three_named_modes() -> None:
    expected = {OUTPUT_MODE_BOTH, OUTPUT_MODE_NOTES, OUTPUT_MODE_TRANSCRIPT}

    assert set(OUTPUT_MODES) == expected
    assert len(OUTPUT_MODES) == len(expected)


def test_script_directory_is_the_app_directory(app_directory: Path) -> None:
    assert SCRIPT_DIRECTORY == app_directory
    assert (SCRIPT_DIRECTORY / 'data.py').is_file()


def test_supported_extensions_are_bare_lowercase_and_unique() -> None:
    extensions = SUPPORTED_AUDIO_EXTENSIONS + SUPPORTED_DOCUMENT_EXTENSIONS

    assert all(extension == extension.lower() for extension in extensions)
    assert all(not extension.startswith('.') for extension in extensions)
    assert len(set(extensions)) == len(extensions)
