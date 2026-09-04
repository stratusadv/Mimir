from __future__ import annotations

import pytest

import document_searcher

from pathlib import Path

from constants import SEARCH_QUERY_CHARACTERS_MAX
from document_searcher import DocumentSearcher
from errors import SearchError
from prompts import SEARCH_INSTRUCTIONS, SEARCH_MERGE_INSTRUCTIONS

from .doubles import FakePolisher


class ChunkingPolisher(FakePolisher):
    def __init__(self, chunks: list[str], findings: list[str], merged: str = 'merged findings') -> None:
        super().__init__(findings_text='')
        self.chunks = chunks
        self.findings = findings
        self.merged = merged

    def chunk_lines(self, lines: list[str], characters_max: int) -> list[str]:
        return list(self.chunks)

    def complete(self, instructions: str, content: str) -> str:
        record = (instructions, content)
        self.completed.append(record)

        if instructions == SEARCH_MERGE_INSTRUCTIONS:
            return self.merged

        search_calls = [call for call in self.completed if call[0] == SEARCH_INSTRUCTIONS]

        return self.findings[len(search_calls) - 1]


def test_format_search_lists_the_query_and_findings(tmp_path: Path) -> None:
    text = DocumentSearcher.format_search(tmp_path / 'contract.docx', 'renewal date', 'found it')

    assert text.startswith('MIMIR SEARCH\ncontract.docx')
    assert 'Query: renewal date' in text
    assert 'found it' in text


def test_output_file_free_adds_a_suffix_when_the_name_is_taken(tmp_path: Path) -> None:
    source_file = tmp_path / 'Quarterly Report.docx'
    (tmp_path / 'quarterly_report_search.txt').write_text('taken', encoding='utf-8')

    output_file = DocumentSearcher.output_file_free(source_file)

    assert output_file.name == 'quarterly_report_search (1).txt'


def test_output_file_free_normalises_the_stem(tmp_path: Path) -> None:
    output_file = DocumentSearcher.output_file_free(tmp_path / 'Quarterly Report.DOCX')

    assert output_file.name == 'quarterly_report_search.txt'


def test_output_file_free_raises_after_too_many_attempts(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    monkeypatch.setattr(document_searcher, 'OUTPUT_ATTEMPTS_MAX', 1)

    (tmp_path / 'report_search.txt').write_text('taken', encoding='utf-8')
    (tmp_path / 'report_search (1).txt').write_text('taken', encoding='utf-8')

    with pytest.raises(SearchError) as error:
        _ = DocumentSearcher.output_file_free(tmp_path / 'report.docx')

    assert 'too many existing files' in str(error.value)


def test_search_contents_raises_when_the_document_has_too_many_sections(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(document_searcher, 'SEARCH_CHUNKS_MAX', 2)

    searcher = DocumentSearcher(ChunkingPolisher(['a', 'b', 'c'], []))

    with pytest.raises(SearchError) as error:
        _ = searcher.search_contents('body', 'query')

    assert 'too large to search' in str(error.value)


def test_search_contents_wraps_each_chunk_with_the_request() -> None:
    searcher = DocumentSearcher(ChunkingPolisher(['first chunk', 'second chunk'], []))
    contents = searcher.search_contents('body', 'renewal date')

    assert len(contents) == 2
    assert contents[0] == 'Request:\nrenewal date\n\nDocument:\nfirst chunk'


def test_search_file_write_writes_the_formatted_text(tmp_path: Path) -> None:
    source_file = tmp_path / 'report.md'
    source_file.write_text('body', encoding='utf-8')
    searcher = DocumentSearcher(FakePolisher())

    output_file = searcher.search_file_write(source_file, 'renewal date', 'found it')

    assert output_file.name == 'report_search.txt'
    assert 'found it' in output_file.read_text(encoding='utf-8')


def test_search_merges_many_chunks() -> None:
    polisher = ChunkingPolisher(['first', 'second'], ['finding one', 'finding two'])
    searcher = DocumentSearcher(polisher)

    assert searcher.search('body', 'renewal date') == 'merged findings'

    merge_calls = [call for call in polisher.completed if call[0] == SEARCH_MERGE_INSTRUCTIONS]

    assert 'finding one' in merge_calls[0][1]
    assert 'finding two' in merge_calls[0][1]


def test_search_raises_when_a_single_chunk_returns_nothing() -> None:
    searcher = DocumentSearcher(ChunkingPolisher(['only chunk'], ['   ']))

    with pytest.raises(SearchError) as error:
        _ = searcher.search('body', 'renewal date')

    assert 'no search findings' in str(error.value)


def test_search_raises_when_every_chunk_returns_nothing() -> None:
    searcher = DocumentSearcher(ChunkingPolisher(['first', 'second'], ['', '']))

    with pytest.raises(SearchError) as error:
        _ = searcher.search('body', 'renewal date')

    assert 'no search findings' in str(error.value)


def test_search_returns_the_single_chunk_findings() -> None:
    searcher = DocumentSearcher(ChunkingPolisher(['only chunk'], ['  found it  ']))

    assert searcher.search('body', 'renewal date') == 'found it'


def test_search_validate_raises_on_an_empty_document() -> None:
    with pytest.raises(SearchError) as error:
        _ = DocumentSearcher.search_validate('   \n  ', 'renewal date')

    assert 'no text to search' in str(error.value)


def test_search_validate_raises_on_an_empty_query() -> None:
    with pytest.raises(SearchError) as error:
        _ = DocumentSearcher.search_validate('body', '   ')

    assert 'search request was empty' in str(error.value)


def test_search_validate_raises_on_an_overlong_query() -> None:
    query = 'x' * (SEARCH_QUERY_CHARACTERS_MAX + 1)

    with pytest.raises(SearchError) as error:
        _ = DocumentSearcher.search_validate('body', query)

    assert 'too long' in str(error.value)


def test_search_validate_strips_both_sides() -> None:
    query_text, source_text = DocumentSearcher.search_validate('  body  ', '  renewal date  ')

    assert query_text == 'renewal date'
    assert source_text == 'body'
