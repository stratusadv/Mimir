from __future__ import annotations

from pathlib import Path

from constants import (
    OUTPUT_ATTEMPTS_MAX,
    POLISH_CHARACTERS_MAX,
    SEARCH_CHUNKS_MAX,
    SEARCH_QUERY_CHARACTERS_MAX,
)
from errors import SearchError
from prompts import SEARCH_INSTRUCTIONS, SEARCH_MERGE_INSTRUCTIONS
from transcript_polisher import TranscriptPolisher


class DocumentSearcher:
    def __init__(self, polisher: TranscriptPolisher) -> None:
        self.polisher = polisher

    @staticmethod
    def format_search(source_file: Path, query: str, findings: str) -> str:
        sections = [
            'MIMIR SEARCH',
            source_file.name,
            '',
            f'Query: {query}',
            '',
            'AI wrote these findings from the document. Check them before you rely on them.',
            '',
            findings,
            '',
        ]

        return '\n'.join(sections)

    @staticmethod
    def output_file_free(source_file: Path) -> Path:
        base_name = source_file.stem.lower().replace(' ', '_')
        output_file = source_file.with_name(f'{base_name}_search.txt')
        attempt = 0

        while output_file.exists():
            attempt += 1

            if attempt > OUTPUT_ATTEMPTS_MAX:
                message = f'too many existing files named {base_name}_search.'
                raise SearchError(message)

            output_file = source_file.with_name(f'{base_name}_search ({attempt}).txt')

        return output_file

    def search(self, document_text: str, query: str) -> str:
        query_text, source_text = self.search_validate(document_text, query)
        contents = self.search_contents(source_text, query_text)

        if len(contents) == 1:
            findings = self.polisher.complete(SEARCH_INSTRUCTIONS, contents[0]).strip()

            if not findings:
                message = 'the text model returned no search findings.'
                raise SearchError(message)

            return findings

        return self.search_merge(contents, query_text)

    def search_contents(self, source_text: str, query_text: str) -> list[str]:
        chunks = self.polisher.chunk_lines(source_text.splitlines(), POLISH_CHARACTERS_MAX)

        if len(chunks) > SEARCH_CHUNKS_MAX:
            message = (
                f'document is too large to search '
                f'({len(chunks)} sections, max {SEARCH_CHUNKS_MAX}).'
            )

            raise SearchError(message)

        contents: list[str] = []

        for chunk in chunks:
            content = f'Request:\n{query_text}\n\nDocument:\n{chunk}'
            contents.append(content)

        return contents

    def search_file_write(self, source_file: Path, query: str, findings: str) -> Path:
        output_file = self.output_file_free(source_file)
        output_text = self.format_search(source_file, query, findings)

        output_file.write_text(output_text, encoding='utf-8')

        return output_file

    def search_merge(self, contents: list[str], query_text: str) -> str:
        findings_chunks = self.polisher.complete_many(SEARCH_INSTRUCTIONS, contents)
        joined_findings = '\n\n'.join(text for text in findings_chunks if text)

        if not joined_findings:
            message = 'the text model returned no search findings.'
            raise SearchError(message)

        merge_content = f'Request:\n{query_text}\n\nSection findings:\n{joined_findings}'
        merged_text = self.polisher.complete(SEARCH_MERGE_INSTRUCTIONS, merge_content).strip()

        if not merged_text:
            message = 'the text model returned no search findings.'
            raise SearchError(message)

        return merged_text

    @staticmethod
    def search_validate(document_text: str, query: str) -> tuple[str, str]:
        query_text = query.strip()
        source_text = document_text.strip()

        if not query_text:
            message = 'search request was empty.'
            raise SearchError(message)

        if len(query_text) > SEARCH_QUERY_CHARACTERS_MAX:
            message = (
                f'search request is too long '
                f'({len(query_text)} characters, max {SEARCH_QUERY_CHARACTERS_MAX}).'
            )

            raise SearchError(message)

        if not source_text:
            message = 'the document has no text to search.'
            raise SearchError(message)

        return query_text, source_text
