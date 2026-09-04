from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

from pathlib import Path
from typing_extensions import Callable

from constants import SUPPORTED_AUDIO_EXTENSIONS, SUPPORTED_DOCUMENT_EXTENSIONS


APP_SCRIPT_NAMES = ('search.bat', 'transcribe.bat')
APP_HELPER_SCRIPT_NAMES = ('version_check.bat',)
CALL_PATTERN = re.compile(r'^\s*call\s+:([A-Za-z0-9_]+)', re.IGNORECASE | re.MULTILINE)
CONFIGURED_ENVIRONMENT = 'AI_API_HOST=https://service.test\nAI_API_KEY=test-key\n'
DYNAMIC_SET_PATTERN = re.compile(r'(?:^|\s)set\s+(?:/a\s+)?"?([A-Za-z0-9_]+)!', re.IGNORECASE | re.MULTILINE)
GOTO_PATTERN = re.compile(r'\bgoto\s+:?([A-Za-z0-9_]+)', re.IGNORECASE)
INHERITED_VARIABLES = frozenset({
    'APPDATA',
    'COMSPEC',
    'ERRORLEVEL',
    'LOCALAPPDATA',
    'PATH',
    'PROGRAMDATA',
    'PROGRAMFILES',
    'RANDOM',
    'SYSTEMROOT',
    'TEMP',
    'TMP',
    'USERNAME',
    'USERPROFILE',
    'WINDIR',
})
LABEL_PATTERN = re.compile(r'^\s*:([A-Za-z0-9_]+)', re.MULTILINE)
OUT_PARAMETER_PATTERN = re.compile(
    r'^\s*call\s+:[A-Za-z0-9_]+\s+[^\r\n]*?\s([A-Za-z_][A-Za-z0-9_]*)[ \t]*$',
    re.IGNORECASE | re.MULTILINE,
)
ROOT_SCRIPT_NAMES = ('setup.bat', 'test.bat', 'uninstall.bat', 'update.bat')
SET_PATTERN = re.compile(r'(?:^|\s)set\s+(?:/a\s+|/p\s+)?"?([A-Za-z0-9_]+)\s*[=+]', re.IGNORECASE | re.MULTILINE)
VARIABLE_PATTERN = re.compile(r'!([A-Za-z0-9_]+)!')

pytestmark = pytest.mark.windows


def batch_files(repository_directory: Path) -> list[Path]:
    names = APP_SCRIPT_NAMES + APP_HELPER_SCRIPT_NAMES
    app_files = [repository_directory / 'app' / name for name in names]
    root_files = [repository_directory / name for name in ROOT_SCRIPT_NAMES]

    return root_files + app_files


def sandbox_built(repository_directory: Path, tmp_path: Path, setup_exit_code: int = 0) -> Path:
    sandbox = tmp_path / 'mimir'
    app_directory = sandbox / 'app'
    app_directory.mkdir(parents=True)

    for name in APP_SCRIPT_NAMES:
        _ = shutil.copy2(repository_directory / 'app' / name, app_directory / name)

    setup_stub = f'@echo off\r\nexit /b {setup_exit_code}\r\n'
    (sandbox / 'setup.bat').write_text(setup_stub, encoding='ascii')

    return sandbox


def script_run(
        script_file: Path,
        arguments: list[str] | None = None,
        input_text: str = '\r\n' * 8,
) -> subprocess.CompletedProcess:
    command = ['cmd.exe', '/c', str(script_file)] + (arguments if arguments else [])

    return subprocess.run(
        command,
        capture_output=True,
        cwd=str(script_file.parent),
        input=input_text,
        text=True,
        timeout=60,
    )


@pytest.fixture(autouse=True)
def windows_only() -> None:
    if os.name != 'nt':
        pytest.skip('the batch scripts only run on Windows')


def test_app_scripts_check_for_the_env_file_beside_themselves(repository_directory: Path) -> None:
    for name in APP_SCRIPT_NAMES:
        text = (repository_directory / 'app' / name).read_text(encoding='utf-8', errors='replace')

        assert 'set "SCRIPT_DIR=%~dp0"' in text
        assert 'if not exist "%SCRIPT_DIR%.env"' in text


def test_env_example_holds_every_key_the_settings_read(repository_directory: Path) -> None:
    example_text = (repository_directory / 'app' / '.env.example').read_text(encoding='utf-8')
    data_text = (repository_directory / 'app' / 'data.py').read_text(encoding='utf-8')
    read_names = set(re.findall(r"'(AI_[A-Z0-9_]+|LLM_[A-Z0-9_]+)'", data_text))
    example_names = set(re.findall(r'^([A-Z_]+)=', example_text, re.MULTILINE))

    assert read_names
    assert read_names <= example_names


def test_every_batch_file_uses_crlf_line_endings(repository_directory: Path) -> None:
    for script_file in batch_files(repository_directory):
        content = script_file.read_bytes()
        bare_newlines = content.replace(b'\r\n', b'')

        assert b'\n' not in bare_newlines, f'{script_file.name} has bare LF line endings'


def test_every_delayed_variable_is_assigned_in_the_same_file(repository_directory: Path) -> None:
    for script_file in batch_files(repository_directory):
        text = script_file.read_text(encoding='utf-8', errors='replace')
        assigned = {name.upper() for name in SET_PATTERN.findall(text)}
        assigned.update(name.upper() for name in OUT_PARAMETER_PATTERN.findall(text))
        prefixes = tuple(prefix.upper() for prefix in DYNAMIC_SET_PATTERN.findall(text))
        referenced = {name.upper() for name in VARIABLE_PATTERN.findall(text)}
        remaining = referenced - assigned - INHERITED_VARIABLES
        unknown = {name for name in remaining if not name.startswith(prefixes)}

        assert not unknown, f'{script_file.name} reads unset variables: {sorted(unknown)}'


def test_every_jump_target_exists(repository_directory: Path) -> None:
    for script_file in batch_files(repository_directory):
        text = script_file.read_text(encoding='utf-8', errors='replace')
        labels = {label.lower() for label in LABEL_PATTERN.findall(text)}
        targets = {target.lower() for target in GOTO_PATTERN.findall(text)}
        targets.update(target.lower() for target in CALL_PATTERN.findall(text))
        missing = targets - labels - {'eof'}

        assert not missing, f'{script_file.name} jumps to missing labels: {sorted(missing)}'


def test_every_script_enables_delayed_expansion(repository_directory: Path) -> None:
    helper_files = {repository_directory / 'app' / name for name in APP_HELPER_SCRIPT_NAMES}

    for script_file in batch_files(repository_directory):
        if script_file in helper_files:
            continue

        text = script_file.read_text(encoding='utf-8', errors='replace')

        assert 'setlocal enabledelayedexpansion' in text.lower()


def test_version_check_sets_what_the_scripts_draw(repository_directory: Path) -> None:
    text = (repository_directory / 'app' / 'version_check.bat').read_text(encoding='utf-8', errors='replace')
    assigned = {name.upper() for name in SET_PATTERN.findall(text)}
    assigned.update(name.upper() for name in OUT_PARAMETER_PATTERN.findall(text))

    assert 'setlocal' not in text.lower()
    assert {'UPDATE_AVAILABLE', 'INSTALLED_VERSION', 'LATEST_VERSION'} <= assigned


def test_the_scripts_draw_the_update_banner_from_the_check(repository_directory: Path) -> None:
    for name in APP_SCRIPT_NAMES:
        text = (repository_directory / 'app' / name).read_text(encoding='utf-8', errors='replace')

        assert 'if exist "%SCRIPT_DIR%version_check.bat" call "%SCRIPT_DIR%version_check.bat"' in text
        assert 'call :draw_update_banner' in text
        assert 'update.bat' in text


def test_search_accepts_the_document_extensions_python_supports(repository_directory: Path) -> None:
    for name in ('app/search.bat', 'setup.bat'):
        text = (repository_directory / name).read_text(encoding='utf-8', errors='replace')
        declared = re.search(r'set "TEXT_EXTENSIONS=([^"]+)"', text).group(1)
        extensions = {entry.strip().lstrip('.') for entry in declared.split() if entry.strip()}

        assert extensions == set(SUPPORTED_DOCUMENT_EXTENSIONS), name


def test_search_reports_a_missing_env_file(
        ansi_stripped: Callable[[str], str],
        repository_directory: Path,
        tmp_path: Path,
) -> None:
    sandbox = sandbox_built(repository_directory, tmp_path)
    result = script_run(sandbox / 'app' / 'search.bat')

    assert 'Missing settings file' in ansi_stripped(result.stdout)


def test_search_reports_a_missing_setup_file(
        ansi_stripped: Callable[[str], str],
        repository_directory: Path,
        tmp_path: Path,
) -> None:
    sandbox = sandbox_built(repository_directory, tmp_path)
    (sandbox / 'setup.bat').unlink()

    result = script_run(sandbox / 'app' / 'search.bat')

    assert 'setup.bat is missing' in ansi_stripped(result.stdout)


def test_setup_reports_the_env_file_from_the_app_directory(repository_directory: Path) -> None:
    text = (repository_directory / 'setup.bat').read_text(encoding='utf-8', errors='replace')

    assert 'set "APP_DIR=%~dp0app\\"' in text
    assert 'if exist "%APP_DIR%.env"' in text


def test_transcribe_accepts_the_audio_extensions_python_supports(repository_directory: Path) -> None:
    text = (repository_directory / 'app' / 'transcribe.bat').read_text(encoding='utf-8', errors='replace')
    declared = re.search(r'set "AUDIO=([^"]+)"', text).group(1)
    extensions = {entry.lstrip('.') for entry in declared.split(';') if entry}

    assert extensions == set(SUPPORTED_AUDIO_EXTENSIONS)


def test_transcribe_reports_a_missing_env_file(
        ansi_stripped: Callable[[str], str],
        repository_directory: Path,
        tmp_path: Path,
) -> None:
    sandbox = sandbox_built(repository_directory, tmp_path)
    result = script_run(sandbox / 'app' / 'transcribe.bat')

    assert 'Missing settings file' in ansi_stripped(result.stdout)


def test_transcribe_reports_a_missing_setup_file(
        ansi_stripped: Callable[[str], str],
        repository_directory: Path,
        tmp_path: Path,
) -> None:
    sandbox = sandbox_built(repository_directory, tmp_path)
    (sandbox / 'setup.bat').unlink()

    result = script_run(sandbox / 'app' / 'transcribe.bat')

    assert 'setup.bat is missing' in ansi_stripped(result.stdout)


def test_transcribe_skips_files_that_are_not_audio(
        ansi_stripped: Callable[[str], str],
        repository_directory: Path,
        tmp_path: Path,
) -> None:
    sandbox = sandbox_built(repository_directory, tmp_path)
    (sandbox / 'app' / '.env').write_text(CONFIGURED_ENVIRONMENT, encoding='ascii')

    document_file = tmp_path / 'notes.pdf'
    document_file.write_bytes(b'pdf')

    result = script_run(sandbox / 'app' / 'transcribe.bat', [str(document_file)], 'Q\r\n')
    text = ansi_stripped(result.stdout)

    assert 'No audio files were dropped' in text or 'ignored - not audio files' in text


def test_transcribe_stops_when_setup_fails(
        ansi_stripped: Callable[[str], str],
        repository_directory: Path,
        tmp_path: Path,
) -> None:
    sandbox = sandbox_built(repository_directory, tmp_path, setup_exit_code=1)
    result = script_run(sandbox / 'app' / 'transcribe.bat')

    assert 'Missing settings file' not in ansi_stripped(result.stdout)
