from pathlib import Path
from textwrap import dedent

from production_rag.ingestion.chunker import MarkdownChunker


def test_chunks_simple_markdown() -> None:
    markdown = dedent("""\
        # Introduction

        FastAPI is a web framework for building APIs.

        It is based on Python type hints.
        """)

    chunks = MarkdownChunker().chunk(markdown)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == (
        "# Introduction\n\n"
        "FastAPI is a web framework for building APIs.\n\n"
        "It is based on Python type hints."
    )
    assert chunks[0].metadata["heading_path"] == ["Introduction"]


def test_chunks_preserve_heading_hierarchy() -> None:
    markdown = dedent("""\
        # Introduction

        Intro text.

        ## Installation

        Install FastAPI.

        ### Requirements

        Python 3.12 is required.
        """)

    chunks = MarkdownChunker().chunk(markdown)

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]

    assert chunks[0].metadata["heading_path"] == ["Introduction"]
    assert chunks[1].metadata["heading_path"] == ["Introduction", "Installation"]
    assert chunks[2].metadata["heading_path"] == [
        "Introduction",
        "Installation",
        "Requirements",
    ]


def test_code_blocks_are_preserved() -> None:

    markdown = dedent("""\
        # Example

        Run the application:

        ```python
        from fastapi import FastAPI

        app = FastAPI()
        ```

        Then open the browser.
        """)

    chunks = MarkdownChunker().chunk(markdown)

    content = "\n\n".join(chunk.content for chunk in chunks)

    assert "```python" in content
    assert "from fastapi import FastAPI" in content
    assert "app = FastAPI()" in content
    assert "```" in content


def test_chunk_indices_are_sequential() -> None:

    markdown = dedent("""\
        # First

        Content.

        # Second

        More content.

        # Third

        More content.
        """)

    chunks = MarkdownChunker().chunk(markdown)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunking_is_deterministic() -> None:
    markdown = dedent("""\
        # Introduction

        Some documentation.

        ## Installation

        More documentation.
        """)

    chunker = MarkdownChunker()

    first = chunker.chunk(markdown)
    second = chunker.chunk(markdown)

    assert first == second


def test_lists_are_preserved() -> None:
    markdown = dedent(
        """\
        # Features

        FastAPI provides:

        - Automatic API documentation
        - Data validation
        - OpenAPI support
        """
    )

    chunks = MarkdownChunker().chunk(markdown)

    assert len(chunks) == 1
    assert "- Automatic API documentation" in chunks[0].content
    assert "- Data validation" in chunks[0].content
    assert "- OpenAPI support" in chunks[0].content


def test_blockquotes_are_preserved() -> None:
    markdown = dedent(
        """\
        # Important

        FastAPI uses standard Python type hints.

        > This is an important note.
        """
    )

    chunks = MarkdownChunker().chunk(markdown)

    assert len(chunks) == 1
    assert "> This is an important note." in chunks[0].content


def test_markdown_source_formatting_is_preserved() -> None:
    markdown = dedent(
        """\
        # Example

        This is **important**.

        - First item
        - Second item

        > Important note
        """
    )

    chunks = MarkdownChunker().chunk(markdown)

    assert len(chunks) == 1
    assert "**important**" in chunks[0].content
    assert "- First item" in chunks[0].content
    assert "- Second item" in chunks[0].content
    assert "> Important note" in chunks[0].content


def test_duplicate_blocks_are_preserved() -> None:
    markdown = dedent(
        """\
        # Example

        This paragraph appears twice.

        This paragraph appears twice.
        """
    )

    chunks = MarkdownChunker().chunk(markdown)

    assert len(chunks) == 1
    assert chunks[0].content.count("This paragraph appears twice.") == 2


def test_long_sections_are_split() -> None:
    markdown = dedent(
        """\
        # Introduction

        First paragraph with some content.

        Second paragraph with more content.

        Third paragraph with additional content.
        """
    )

    chunks = MarkdownChunker(max_characters=60).chunk(markdown)

    assert len(chunks) > 1
    assert all(chunk.content for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_split_chunks_preserve_heading_path() -> None:
    markdown = dedent(
        """\
        # Introduction

        First paragraph with some content.

        Second paragraph with more content.

        Third paragraph with additional content.
        """
    )

    chunks = MarkdownChunker(max_characters=60).chunk(markdown)

    assert len(chunks) > 1
    assert all(chunk.metadata["heading_path"] == ["Introduction"] for chunk in chunks)


def test_code_blocks_are_not_split() -> None:
    code = "\n".join(f"print({i})" for i in range(20))

    markdown = f"# Example\n\nSome explanation.\n\n```python\n{code}\n```\n"

    chunks = MarkdownChunker(max_characters=50).chunk(markdown)

    code_chunks = [chunk for chunk in chunks if "```python" in chunk.content]

    assert len(code_chunks) == 1
    assert code_chunks[0].content.count("print(") == 20


def test_fastapi_corpus_can_be_chunked() -> None:
    corpus_dir = Path("data/raw/fastapi")
    chunker = MarkdownChunker()

    files = sorted(corpus_dir.glob("*.md"))

    assert files

    for path in files:
        chunks = chunker.chunk(path.read_text())

        assert chunks, f"No chunks produced for {path}"
        assert all(chunk.content.strip() for chunk in chunks)
        assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
