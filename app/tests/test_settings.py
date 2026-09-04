from __future__ import annotations

import os

import pytest

import data

from pathlib import Path
from typing_extensions import Callable

from constants import OUTPUT_MODE_BOTH, OUTPUT_MODE_NOTES, OUTPUT_MODE_TRANSCRIPT
from data import TranscriptionSettings


CONFIGURED_ENVIRONMENT = 'AI_API_HOST=https://service.test\nAI_API_KEY=test-key\n'


def test_base_url_appends_version_segment(settings_factory: Callable[..., TranscriptionSettings]) -> None:
    settings = settings_factory(api_host='https://service.test')

    assert settings.base_url == 'https://service.test/v1'


def test_base_url_doubles_slash_when_host_has_trailing_slash(
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    settings = settings_factory(api_host='https://service.test/')

    assert settings.base_url == 'https://service.test//v1'


def test_configuration_detail_names_both_missing_keys(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written('LLM_TEXT_MODEL=stratus.thinking\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.missing_names == ['AI_API_HOST', 'AI_API_KEY']
    assert 'AI_API_HOST and AI_API_KEY are empty or missing' in settings.configuration_detail
    assert str(settings.environment_file) in settings.configuration_detail


def test_configuration_detail_names_one_missing_key(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written('AI_API_HOST=https://service.test\nAI_API_KEY=\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.missing_names == ['AI_API_KEY']
    assert 'AI_API_KEY is empty or missing' in settings.configuration_detail
    assert 'AI_API_HOST' not in settings.configuration_detail


def test_configuration_detail_points_at_a_missing_file(
        environment_file_written: Callable[..., Path],
) -> None:
    settings = TranscriptionSettings.from_environment()

    assert 'No settings file was found' in settings.configuration_detail
    assert 'Copy .env.example to .env' in settings.configuration_detail
    assert str(settings.environment_file.parent) in settings.configuration_detail


def test_configuration_detail_reports_a_line_without_an_equals_sign(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written('# a comment\nAI_API_HOST https://service.test\nAI_API_KEY=test-key\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.has_unparsable_lines
    assert 'some lines have no = sign' in settings.configuration_detail


def test_configuration_detail_stays_quiet_about_comments_and_blank_lines(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written('# a comment\n\n   \nAI_API_KEY=test-key\n')
    settings = TranscriptionSettings.from_environment()

    assert not settings.has_unparsable_lines
    assert 'no = sign' not in settings.configuration_detail


def test_from_environment_accepts_bom_prefixed_file(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written(b'\xef\xbb\xbf' + CONFIGURED_ENVIRONMENT.encode('utf-8'))
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured
    assert settings.api_host == 'https://service.test'


def test_from_environment_accepts_crlf_line_endings(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT.replace('\n', '\r\n'))
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured


def test_from_environment_accepts_example_placeholder_values(
        app_directory: Path,
        environment_file_written: Callable[..., Path],
) -> None:
    example_text = (app_directory / '.env.example').read_text(encoding='utf-8')
    _ = environment_file_written(example_text)
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured
    assert settings.api_key == 'your-key-here'


def test_from_environment_accepts_export_prefix(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written('export AI_API_HOST=https://service.test\nexport AI_API_KEY=test-key\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured


def test_from_environment_accepts_inline_comment(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written('AI_API_HOST=https://service.test # host\nAI_API_KEY=test-key # key\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.api_host == 'https://service.test'
    assert settings.api_key == 'test-key'


def test_from_environment_accepts_quoted_values(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written('AI_API_HOST="https://service.test"\nAI_API_KEY=\'test-key\'\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.api_host == 'https://service.test'
    assert settings.api_key == 'test-key'


def test_from_environment_accepts_spaces_around_equals(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written('AI_API_HOST = https://service.test\nAI_API_KEY = test-key\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured


def test_from_environment_blank_value_is_not_configured(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written('AI_API_HOST=\nAI_API_KEY=\n')
    settings = TranscriptionSettings.from_environment()

    assert not settings.is_configured


def test_from_environment_curly_quotes_are_kept_in_the_value(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written('AI_API_HOST=“https://service.test”\nAI_API_KEY=test-key\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured
    assert settings.api_host == '“https://service.test”'


def test_from_environment_ignores_env_file_in_the_parent_directory(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    parent_directory = tmp_path / 'mimir'
    app_directory = parent_directory / 'app'
    app_directory.mkdir(parents=True)

    (parent_directory / '.env').write_text(CONFIGURED_ENVIRONMENT, encoding='utf-8')
    monkeypatch.setattr(data, 'SCRIPT_DIRECTORY', app_directory)

    settings = TranscriptionSettings.from_environment()

    assert not settings.is_configured


def test_from_environment_missing_file_is_not_configured(environment_file_written: Callable[..., Path]) -> None:
    settings = TranscriptionSettings.from_environment()

    assert settings.api_host is None
    assert settings.api_key is None
    assert not settings.is_configured


def test_from_environment_normalises_output_mode(
        environment_file_written: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT)
    monkeypatch.setenv('MIMIR_OUTPUT_MODE', '  BOTH  ')

    settings = TranscriptionSettings.from_environment()

    assert settings.output_mode == OUTPUT_MODE_BOTH


def test_from_environment_reads_defaults_for_optional_keys(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT)
    settings = TranscriptionSettings.from_environment()

    assert settings.audio_model == 'stratus.listen'
    assert settings.output_mode == OUTPUT_MODE_TRANSCRIPT
    assert settings.result_file is None
    assert settings.search_query == ''
    assert settings.text_model == 'stratus.thinking'


def test_from_environment_reads_result_file_and_query(
        environment_file_written: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT)
    result_file = tmp_path / 'result.txt'

    monkeypatch.setenv('MIMIR_RESULT_FILE', str(result_file))
    monkeypatch.setenv('MIMIR_SEARCH_QUERY', '   action items   ')

    settings = TranscriptionSettings.from_environment()

    assert settings.result_file == result_file
    assert settings.search_query == 'action items'


def test_from_environment_prefers_the_env_file_over_a_stale_process_variable(
        environment_file_written: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT)
    monkeypatch.setenv('AI_API_KEY', 'stale-key')

    settings = TranscriptionSettings.from_environment()

    assert settings.api_key == 'test-key'


def test_from_environment_falls_back_to_a_process_variable(
        environment_file_written: Callable[..., Path],
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = environment_file_written('AI_API_HOST=https://service.test\n')
    monkeypatch.setenv('AI_API_KEY', 'process-key')

    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured
    assert settings.api_key == 'process-key'


def test_from_environment_leaves_the_process_environment_alone(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT)
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured
    assert os.getenv('AI_API_KEY') is None


def test_from_environment_unparsable_line_is_skipped_silently(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written('AI_API_HOST https://service.test\nAI_API_KEY: test-key\n')
    settings = TranscriptionSettings.from_environment()

    assert settings.api_host is None
    assert settings.api_key is None
    assert not settings.is_configured


def test_from_environment_reads_a_utf16_file(environment_file_written: Callable[..., Path]) -> None:
    _ = environment_file_written(CONFIGURED_ENVIRONMENT.encode('utf-16'))
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured
    assert settings.api_host == 'https://service.test'


def test_from_environment_reads_a_utf16_big_endian_file(
        environment_file_written: Callable[..., Path],
) -> None:
    _ = environment_file_written(b'\xfe\xff' + CONFIGURED_ENVIRONMENT.encode('utf-16-be'))
    settings = TranscriptionSettings.from_environment()

    assert settings.is_configured


def test_is_configured_requires_both_host_and_key(
        settings_factory: Callable[..., TranscriptionSettings],
) -> None:
    assert settings_factory().is_configured
    assert not settings_factory(api_host=None).is_configured
    assert not settings_factory(api_key=None).is_configured
    assert not settings_factory(api_host='', api_key='').is_configured


@pytest.mark.parametrize(
    ('output_mode', 'keeps_transcript', 'writes_notes'),
    [
        (OUTPUT_MODE_BOTH, True, True),
        (OUTPUT_MODE_NOTES, False, True),
        (OUTPUT_MODE_TRANSCRIPT, True, False),
        ('unknown', False, False),
    ],
)
def test_output_mode_flags(
        settings_factory: Callable[..., TranscriptionSettings],
        output_mode: str,
        keeps_transcript: bool,
        writes_notes: bool,
) -> None:
    settings = settings_factory(output_mode=output_mode)

    assert settings.keeps_transcript is keeps_transcript
    assert settings.writes_notes is writes_notes


def test_process_environment_is_isolated_between_tests() -> None:
    assert os.getenv('AI_API_KEY') is None
    assert os.getenv('MIMIR_OUTPUT_MODE') is None
