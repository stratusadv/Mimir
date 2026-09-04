from __future__ import annotations

from pathlib import Path
from typing_extensions import Any, Callable

from audio_chunker import AudioChunkSet
from console import Console
from data import TranscriptNotes


class FakeAudioChunker:
    def __init__(
            self,
            chunk_files: list[Path],
            temp_directory: Path,
            segment_length_seconds: int = 30,
    ) -> None:
        self.chunk_files = chunk_files
        self.segment_length_seconds = segment_length_seconds
        self.temp_directory = temp_directory

    def chunk(self, audio_file: Path) -> AudioChunkSet:
        return AudioChunkSet(list(self.chunk_files), self.temp_directory)


class FakeAudioNamespace:
    def __init__(self, transcriptions: FakeTranscriptions) -> None:
        self.transcriptions = transcriptions


class FakeChatCompletions:
    def __init__(self, responder: Callable[[list[dict], str], str | None]) -> None:
        self.calls: list[dict] = []
        self.responder = responder

    def create(self, **keywords: Any) -> FakeCompletion:
        self.calls.append(keywords)
        text = self.responder(keywords['messages'], keywords['model'])

        return FakeCompletion(text)


class FakeChatNamespace:
    def __init__(self, completions: FakeChatCompletions) -> None:
        self.completions = completions


class FakeChoice:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message


class FakeCompletion:
    def __init__(self, text: str | None) -> None:
        message = FakeMessage(text)
        choice = FakeChoice(message)

        self.choices = [choice]


class FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeOpenAI:
    audio_responder: Callable[[str], str | None] = staticmethod(lambda name: 'chunk text')
    instances: list[FakeOpenAI] = []
    text_responder: Callable[[list[dict], str], str | None] = staticmethod(lambda messages, model: 'model text')

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.audio = FakeAudioNamespace(FakeTranscriptions(type(self).audio_responder))
        self.chat = FakeChatNamespace(FakeChatCompletions(type(self).text_responder))

        type(self).instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances = []


class FakePolisher:
    def __init__(
            self,
            cleaned_text: str = 'cleaned',
            summary_text: str = 'summary',
            findings_text: str = 'findings',
            error: Exception | None = None,
    ) -> None:
        self.cleaned_text = cleaned_text
        self.completed: list[tuple[str, str]] = []
        self.error = error
        self.findings_text = findings_text
        self.summary_text = summary_text

    def chunk_lines(self, lines: list[str], characters_max: int) -> list[str]:
        return ['\n'.join(lines)] if lines else ['']

    def complete(self, instructions: str, content: str) -> str:
        record = (instructions, content)
        self.completed.append(record)

        return self.findings_text

    def complete_many(self, instructions: str, contents: list[str]) -> list[str]:
        return [self.complete(instructions, content) for content in contents]

    def polish(self, transcript_text: str) -> TranscriptNotes:
        if self.error:
            raise self.error

        return TranscriptNotes(cleaned_text=self.cleaned_text, summary_text=self.summary_text)


class FakeTranscription:
    def __init__(self, text: str | None, error: dict | None = None) -> None:
        self.error = error
        self.text = text


class FakeTranscriptionClient:
    def __init__(self, texts: dict[str, str], failures: set[str] | None = None) -> None:
        self.failures = failures if failures else set()
        self.requested: list[str] = []
        self.texts = texts

    def transcribe_chunk(self, audio_chunk_file: Path) -> str:
        self.requested.append(audio_chunk_file.name)

        if audio_chunk_file.name in self.failures:
            message = f'chunk {audio_chunk_file.name} failed'
            raise RuntimeError(message)

        return self.texts.get(audio_chunk_file.name, '')


class FakeTranscriptions:
    def __init__(self, responder: Callable[[str], str | None]) -> None:
        self.calls: list[dict] = []
        self.responder = responder

    def create(self, **keywords: Any) -> FakeTranscription:
        self.calls.append(keywords)
        text = self.responder(keywords['file'].name)

        return FakeTranscription(text)


class SilentConsole(Console):
    def __init__(self, save_answer: bool = True) -> None:
        self.events: list[tuple] = []
        self.save_answer = save_answer

    def error(self, message: str, detail: str = '') -> None:
        record = ('error', message, detail)
        self.events.append(record)

    def event_names(self) -> list[str]:
        return [event[0] for event in self.events]

    def events_named(self, name: str) -> list[tuple]:
        return [event for event in self.events if event[0] == name]

    def failure(self, audio_file: Path, error: Exception) -> None:
        record = ('failure', audio_file.name, str(error))
        self.events.append(record)

    def gaps(self, gap_count: int, gap_seconds: int) -> None:
        record = ('gaps', gap_count, gap_seconds)
        self.events.append(record)

    def interrupted(self) -> None:
        record = ('interrupted',)
        self.events.append(record)

    def notes(self, notes_file: Path) -> None:
        record = ('notes', notes_file.name)
        self.events.append(record)

    def notes_failure(self, error: Exception) -> None:
        record = ('notes_failure', str(error))
        self.events.append(record)

    def notes_start(self, audio_file: Path) -> None:
        record = ('notes_start', audio_file.name)
        self.events.append(record)

    def progress(self, audio_file: Path, complete_count: int, chunk_count: int) -> None:
        record = ('progress', audio_file.name, complete_count, chunk_count)
        self.events.append(record)

    def search_failure(self, error: Exception) -> None:
        record = ('search_failure', str(error))
        self.events.append(record)

    def search_findings(self, output_text: str) -> None:
        record = ('search_findings', output_text)
        self.events.append(record)

    def search_ok(self, source_file: Path, elapsed_seconds: float) -> None:
        record = ('search_ok', source_file.name)
        self.events.append(record)

    def search_save_ask(self) -> bool:
        record = ('search_save_ask',)
        self.events.append(record)

        return self.save_answer

    def search_saved(self, output_file: Path) -> None:
        record = ('search_saved', output_file.name)
        self.events.append(record)

    def search_skipped(self) -> None:
        record = ('search_skipped',)
        self.events.append(record)

    def search_start(self, source_file: Path, query: str) -> None:
        record = ('search_start', source_file.name, query)
        self.events.append(record)

    def start(self, audio_file: Path) -> None:
        record = ('start', audio_file.name)
        self.events.append(record)

    def success(self, audio_file: Path, output_file: Path, elapsed_seconds: float) -> None:
        record = ('success', audio_file.name, output_file.name)
        self.events.append(record)

    def summary(
            self,
            success_count: int,
            fail_count: int,
            gap_file_count: int,
            gap_count: int,
            *,
            success_label: str = 'transcribed',
    ) -> None:
        record = ('summary', success_count, fail_count, gap_file_count, gap_count, success_label)
        self.events.append(record)

    def warning(self, message: str) -> None:
        record = ('warning', message)
        self.events.append(record)
