from dataclasses import dataclass
from typing import Any

from markdown_it import MarkdownIt


@dataclass(frozen=True, slots=True)
class ChunkData:
    content: str
    chunk_index: int
    token_count: int | None
    metadata: dict[str, Any]


class MarkdownChunker:
    def __init__(self, max_characters: int = 4000) -> None:
        if max_characters <= 0:
            raise ValueError("max_characters must be greater than zero")

        self.max_characters = max_characters
        self.parser = MarkdownIt()

    def chunk(self, content: str) -> list[ChunkData]:
        lines = content.splitlines()
        tokens = self.parser.parse(content)

        chunks: list[ChunkData] = []
        heading_path: list[str] = []
        current_blocks: list[str] = []
        index = 0

        def flush() -> None:
            nonlocal index
            if not current_blocks:
                return

            chunks.append(
                self._create_chunk(
                    current_blocks,
                    index,
                    heading_path,
                )
            )
            index += 1
            current_blocks.clear()

        def add_block(block: str) -> None:
            if not block:
                return

            if not current_blocks:
                current_blocks.append(block)
                return

            candidate = "\n\n".join([*current_blocks, block])

            if len(candidate) <= self.max_characters:
                current_blocks.append(block)
                return

            flush()
            current_blocks.append(block)

        i = 0

        while i < len(tokens):
            token = tokens[i]

            if token.type == "heading_open":
                flush()

                level = int(token.tag[1])
                heading = tokens[i + 1].content

                while len(heading_path) >= level:
                    heading_path.pop()

                heading_path.append(heading)

                block = self._source_block(lines, token)
                add_block(block)

                i += 3
                continue

            if token.type == "fence":
                block = self._source_block(lines, token)
                add_block(block)

                i += 1
                continue

            if token.nesting == 1 and token.map is not None:
                block = self._source_block(lines, token)
                add_block(block)

            i += 1

        flush()

        return chunks

    @staticmethod
    def _source_block(lines: list[str], token: Any) -> str:
        if token.map is None:
            return ""

        start, end = token.map
        return "\n".join(lines[start:end]).strip()

    @staticmethod
    def _create_chunk(
        blocks: list[str],
        index: int,
        heading_path: list[str],
    ) -> ChunkData:
        return ChunkData(
            content="\n\n".join(blocks),
            chunk_index=index,
            token_count=None,
            metadata={"heading_path": heading_path.copy()},
        )
