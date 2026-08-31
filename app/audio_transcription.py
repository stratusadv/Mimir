# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

from __future__ import annotations

import logging
import os
import sys

from types import TracebackType

from console import Console
from constants import LOG_PATH
from data import TranscriptionSettings
from transcription_manager import TranscriptionManager


log = logging.getLogger('mimir')


def configure_logging() -> None:
    if log.handlers:
        return

    if LOG_PATH.exists() and LOG_PATH.stat().st_size:
        with LOG_PATH.open('a', encoding='utf-8') as log_file:
            log_file.write('\n')

    formatter = logging.Formatter(
        fmt='%(asctime)s  %(levelname)-8s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    try:
        handler = logging.FileHandler(LOG_PATH, encoding='utf-8')

    except OSError:
        print(f'   could not write log file: {LOG_PATH}', file=sys.stderr)

        return

    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    logging.captureWarnings(True)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.WARNING)
    sys.excepthook = unhandled_exception


def main() -> int:
    configure_logging()
    Console.enable_ansi_colors()
    settings = TranscriptionSettings.from_environment()
    manager = TranscriptionManager(settings)

    log.info(
        'session start  python=%s  output_mode=%s  audio_model=%s  text_model=%s  host=%s  key=%s',
        sys.version.split()[0],
        settings.output_mode,
        settings.audio_model,
        settings.text_model,
        settings.api_host or '(missing)',
        'set' if settings.api_key else 'missing',
    )

    try:
        exit_code = manager.run()

    except KeyboardInterrupt:
        manager.console.interrupted()
        log.warning('session interrupted')
        logging.shutdown()
        os._exit(130)

    log.info(
        'session end  transcribed=%s  failed=%s  gaps=%s',
        manager.success_count,
        manager.fail_count,
        manager.gap_count,
    )

    return exit_code


def unhandled_exception(
    exception_type: type[BaseException],
    exception: BaseException,
    traceback_object: TracebackType | None,
) -> None:
    log.exception(
        'unhandled exception',
        exc_info=(exception_type, exception, traceback_object),
    )

    sys.__excepthook__(exception_type, exception, traceback_object)


if __name__ == '__main__':
    sys.exit(main())
