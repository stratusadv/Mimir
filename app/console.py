from __future__ import annotations

import ctypes
import os

from pathlib import Path

from constants import LOG_PATH


class Console:
    ACCENT = '\033[96m'
    CLEAR_LINE = '\033[2K\033[G'
    FAIL = '\033[91m'
    MUTED = '\033[90m'
    OK = '\033[92m'
    RESET = '\033[0m'
    RULE = '--------------------------------------------------------------------'
    WARN = '\033[93m'

    @staticmethod
    def enable_ansi_colors() -> None:
        if os.name != 'nt':
            return

        kernel32 = ctypes.windll.kernel32
        _ = kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    def error(self, message: str, detail: str = '') -> None:
        print(f'   {self.FAIL}[ERROR]{self.RESET} {message}')

        if detail:
            print(f'   {self.MUTED}{detail}{self.RESET}')

    def failure(self, audio_file: Path, error: Exception) -> None:
        print(f'{self.CLEAR_LINE}   {self.FAIL}[FAIL]{self.RESET} {audio_file.name}')
        print(f'         {self.MUTED}{error}{self.RESET}')

    def gaps(self, gap_count: int, gap_seconds: int) -> None:
        piece_label = 'piece' if gap_count == 1 else 'pieces'

        print(
            f'         {self.WARN}{gap_count} {piece_label} could not be transcribed; '
            f'{gap_seconds} seconds marked [inaudible] in the transcript{self.RESET}'
        )

    def interrupted(self) -> None:
        print(f'{self.CLEAR_LINE}   {self.WARN}[STOP]{self.RESET} interrupted')

    def notes(self, notes_file: Path) -> None:
        print(f'         {self.MUTED}notes{self.RESET} {self.OK}{notes_file.name}{self.RESET}')

    def notes_failure(self, error: Exception) -> None:
        print(f'         {self.WARN}Notes could not be written; the transcript is unchanged.{self.RESET}')
        print(f'         {self.MUTED}{error}{self.RESET}')

    def notes_start(self, audio_file: Path) -> None:
        print(
            f'{self.CLEAR_LINE}{self.MUTED}   [ .. ] writing notes for {audio_file.name}{self.RESET}',
            end='',
            flush=True,
        )

    def progress(self, audio_file: Path, complete_count: int, chunk_count: int) -> None:
        percentage_complete = complete_count / chunk_count * 100

        print(
            f'{self.CLEAR_LINE}{self.MUTED}   [ {percentage_complete:3.0f}% ] '
            f'{audio_file.name} {self.RESET}{self.MUTED}'
            f'({complete_count} of {chunk_count} pieces){self.RESET}',
            end='',
            flush=True,
        )

    def start(self, audio_file: Path) -> None:
        print(f'{self.MUTED}   [  0% ] {audio_file.name}{self.RESET}', end='', flush=True)

    def success(self, audio_file: Path, output_file: Path, elapsed_seconds: float) -> None:
        print(
            f'{self.CLEAR_LINE}   {self.OK}[ OK ]{self.RESET} {audio_file.name} '
            f'{self.MUTED}->{self.RESET} {self.OK}{output_file.name}{self.RESET}'
        )

        print(f'         {self.MUTED}{elapsed_seconds:.0f} seconds{self.RESET}')

    def summary(self, success_count: int, fail_count: int, gap_file_count: int, gap_count: int) -> None:
        print()
        print(f'   {self.MUTED}{self.RULE}{self.RESET}')
        print(f'    {self.OK}{success_count} transcribed{self.RESET}   {self.FAIL}{fail_count} failed{self.RESET}')

        if gap_count:
            file_label = 'file' if gap_file_count == 1 else 'files'
            piece_label = 'piece' if gap_count == 1 else 'pieces'

            print(
                f'    {self.WARN}{gap_count} audio {piece_label} missing across '
                f'{gap_file_count} {file_label}; search transcripts for [inaudible]{self.RESET}'
            )

        if fail_count or gap_count:
            print(f'    {self.MUTED}details: {LOG_PATH}{self.RESET}')

    def warning(self, message: str) -> None:
        print(f'   {self.WARN}{message}{self.RESET}')
