from __future__ import annotations

import sys

from pathlib import Path


APP_DIRECTORY = Path(__file__).resolve().parent.parent
AUDIO_FIXTURE_DIRECTORY = Path(__file__).resolve().parent / 'audo_files'
REPOSITORY_DIRECTORY = APP_DIRECTORY.parent

if str(APP_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(APP_DIRECTORY))
