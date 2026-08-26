from pathlib import Path

from production_rag import build_parser


def test_ingest_command_parses_arguments():
    parser = build_parser()

    args = parser.parse_args(
        [
            "ingest",
            "--path",
            "data/raw/fastapi",
            "--collection",
            "fastapi",
        ]
    )

    assert args.command == "ingest"
    assert args.path == Path("data/raw/fastapi")
    assert args.collection == "fastapi"
