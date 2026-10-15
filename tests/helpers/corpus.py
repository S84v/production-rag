"""Shared fixtures for corpus preparation tests."""

from pathlib import Path

PROSE = (
    "This paragraph exists so the prepared document contains enough prose words "
    "to be considered documentation rather than generated reference material. "
    "It deliberately uses complete sentences with several ordinary words so the "
    "prose detector counts it as substantive human written documentation."
)


def build_checkout(root: Path) -> Path:
    """Create a minimal synthetic FastAPI checkout under ``root``.

    The layout mirrors the upstream one (``docs/en/docs`` plus ``docs_src``) but
    is not a Git repository, so tests call ``prepare_corpus`` with
    ``verify_revision=False``.
    """

    docs_root = root / "docs/en/docs"

    (docs_root / "tutorial").mkdir(parents=True)
    (docs_root / "tutorial/example.md").write_text(
        "# Example\n\n"
        "{* ../../docs_src/demo/example.py hl[6:7] *}\n\n"
        "Inline fence variant:\n\n"
        "```python\n{!../../docs_src/demo/example.py!}\n```\n\n"
        f"{PROSE}\n",
        encoding="utf-8",
    )

    (docs_root / "advanced").mkdir(parents=True)
    (docs_root / "advanced/example.md").write_text(
        f"# Advanced {{ #advanced }}\n\n{PROSE}\n",
        encoding="utf-8",
    )

    (docs_root / "reference").mkdir(parents=True)
    (docs_root / "reference/stub.md").write_text(
        "# Reference\n\n::: fastapi.Thing\n",
        encoding="utf-8",
    )

    (docs_root / "features.md").write_text(
        f"# Features\n\n{PROSE}\n",
        encoding="utf-8",
    )

    (root / "docs_src/demo").mkdir(parents=True)
    (root / "docs_src/demo/example.py").write_text(
        "from fastapi import FastAPI\n"
        "\n"
        "app = FastAPI()\n"
        "\n"
        "\n"
        '@app.get("/items/{item_id}")\n'
        "def read_item(item_id: int):\n"
        "    return item_id\n",
        encoding="utf-8",
    )

    return root
