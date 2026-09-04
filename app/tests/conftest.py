from __future__ import annotations

import os
import re
import shutil
import tempfile

import pytest

import data

from pathlib import Path
from typing_extensions import Callable

from data import TranscriptionSettings

from . import APP_DIRECTORY, AUDIO_FIXTURE_DIRECTORY, REPOSITORY_DIRECTORY


ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
ENVIRONMENT_PREFIXES = ('AI_API_', 'LLM_', 'MIMIR_')
REMOVABLE_ROOTS = (Path(tempfile.gettempdir()).resolve(),)


@pytest.fixture
def ansi_stripped() -> Callable[[str], str]:
    def strip(text: str) -> str:
        return ANSI_PATTERN.sub('', text)

    return strip


@pytest.fixture
def app_directory() -> Path:
    return APP_DIRECTORY


@pytest.fixture
def audio_fixture_directory() -> Path:
    return AUDIO_FIXTURE_DIRECTORY


@pytest.fixture(autouse=True)
def environment_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.upper().startswith(ENVIRONMENT_PREFIXES):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def environment_file_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[..., Path]:
    def write(content: bytes | str, encoding: str = 'utf-8') -> Path:
        environment_file = tmp_path / '.env'
        payload = content if isinstance(content, bytes) else content.encode(encoding)

        environment_file.write_bytes(payload)

        return environment_file

    monkeypatch.setattr(data, 'SCRIPT_DIRECTORY', tmp_path)

    return write


@pytest.fixture
def repository_directory() -> Path:
    return REPOSITORY_DIRECTORY


@pytest.fixture(autouse=True)
def repository_tree_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    rmtree_original = shutil.rmtree

    def rmtree_guarded(path, *arguments, **keywords) -> None:
        target = Path(path).resolve()

        if not any(target.is_relative_to(root) for root in REMOVABLE_ROOTS):
            message = (
                f'a test tried to remove {target}, which is outside the '
                f'temporary directory; only trees under {REMOVABLE_ROOTS[0]} may be removed'
            )

            raise AssertionError(message)

        rmtree_original(path, *arguments, **keywords)

    monkeypatch.setattr(shutil, 'rmtree', rmtree_guarded)

    yield

    assert (APP_DIRECTORY / 'data.py').is_file(), 'the working tree was damaged by a test'


@pytest.fixture
def settings(settings_factory: Callable[..., TranscriptionSettings]) -> TranscriptionSettings:
    return settings_factory()


@pytest.fixture
def settings_factory(tmp_path: Path) -> Callable[..., TranscriptionSettings]:
    def build(**overrides) -> TranscriptionSettings:
        values = {
            'api_host': 'https://service.test',
            'api_key': 'test-key',
            'audio_model': 'stratus.listen',
            'chunk_workers_max': 2,
            'environment_file': tmp_path / '.env',
            'output_mode': 'transcript',
            'result_file': None,
            'search_query': '',
            'segment_length_seconds': 30,
            'text_model': 'stratus.thinking',
        }

        values.update(overrides)

        return TranscriptionSettings(**values)

    return build


@pytest.fixture(autouse=True)
def working_directory_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    working_directory = tmp_path / 'cwd'
    working_directory.mkdir(exist_ok=True)

    monkeypatch.chdir(working_directory)
