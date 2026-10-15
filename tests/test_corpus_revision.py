"""The preparation step must verify the pinned checkout revision.

Provenance is only trustworthy if the checkout is the pinned revision, and a
manifest must never claim that pin otherwise. The Git lookup is read locally
(``git rev-parse HEAD``) and is stubbed here so the tests stay hermetic.
"""

import json
import subprocess

import pytest

from production_rag.corpus import preparation
from production_rag.corpus.preparation import (
    MANIFEST_NAME,
    PINNED_REVISION,
    PreparationError,
    prepare_corpus,
    verify_checkout_revision,
)
from tests.helpers.corpus import build_checkout


def stub_run(*, returncode: int = 0, stdout: str = "", stderr: str = ""):
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=returncode, stdout=stdout, stderr=stderr
        )

    return runner


def test_verify_checkout_revision_accepts_the_pin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        preparation.subprocess, "run", stub_run(stdout=f"{PINNED_REVISION}\n")
    )

    assert verify_checkout_revision(tmp_path) == PINNED_REVISION


def test_verify_checkout_revision_rejects_a_mismatched_revision(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(preparation.subprocess, "run", stub_run(stdout="deadbeef\n"))

    with pytest.raises(PreparationError) as excinfo:
        verify_checkout_revision(tmp_path)

    assert "expected the pinned revision" in str(excinfo.value)


def test_verify_checkout_revision_reports_a_missing_repository(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        preparation.subprocess,
        "run",
        stub_run(
            returncode=128,
            stderr=(
                "fatal: not a git repository (or any of the parent directories): .git"
            ),
        ),
    )

    with pytest.raises(PreparationError) as excinfo:
        verify_checkout_revision(tmp_path)

    assert "is not a Git checkout" in str(excinfo.value)


def test_verify_checkout_revision_reports_a_failed_lookup(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        preparation.subprocess,
        "run",
        stub_run(returncode=128, stderr="fatal: ambiguous argument 'HEAD'"),
    )

    with pytest.raises(PreparationError) as excinfo:
        verify_checkout_revision(tmp_path)

    assert "failed to read the Git revision" in str(excinfo.value)


def test_verify_checkout_revision_reports_empty_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(preparation.subprocess, "run", stub_run(stdout=""))

    with pytest.raises(PreparationError) as excinfo:
        verify_checkout_revision(tmp_path)

    assert "empty output" in str(excinfo.value)


def test_verify_checkout_revision_reports_missing_git(tmp_path, monkeypatch) -> None:
    def runner(args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(preparation.subprocess, "run", runner)

    with pytest.raises(PreparationError) as excinfo:
        verify_checkout_revision(tmp_path)

    assert "git executable not found" in str(excinfo.value)


def test_prepare_corpus_verifies_before_writing_anything(tmp_path, monkeypatch) -> None:
    root = build_checkout(tmp_path)
    dest = tmp_path / "out"

    def fail_verification(*args, **kwargs):
        raise PreparationError(["checkout revision does not match the pin"])

    monkeypatch.setattr(preparation, "verify_checkout_revision", fail_verification)

    with pytest.raises(PreparationError):
        prepare_corpus(checkout_root=root, dest_root=dest)

    assert not dest.exists()


def test_manifest_records_the_pin_only_when_verified(tmp_path, monkeypatch) -> None:
    root = build_checkout(tmp_path)

    unverified_dest = tmp_path / "unverified"
    prepare_corpus(checkout_root=root, dest_root=unverified_dest, verify_revision=False)

    unverified_manifest = json.loads(
        (unverified_dest / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert unverified_manifest["pinned_revision"] is None

    monkeypatch.setattr(
        preparation, "verify_checkout_revision", lambda *a, **k: PINNED_REVISION
    )

    verified_dest = tmp_path / "verified"
    prepare_corpus(checkout_root=root, dest_root=verified_dest)

    verified_manifest = json.loads(
        (verified_dest / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert verified_manifest["pinned_revision"] == PINNED_REVISION
