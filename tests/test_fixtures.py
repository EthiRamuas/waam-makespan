"""Copied reference configs must stay byte-identical to the Validator repo's (DECISIONS.md C-05)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "model01" / "config.yaml"
ORIGINAL = Path("C:/Github/WAAM_Validator/tests/01/config.yaml")
# md5 of the shared config (docs/spec.md: all six tests/NN configs are identical)
EXPECTED_MD5 = "bf3b30c6e762bcc93ff44d8f80bcb46d"


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_model01_fixture_md5_is_pinned():
    assert FIXTURE.exists(), "tests/fixtures/model01/config.yaml missing (C-05)"
    assert _md5(FIXTURE) == EXPECTED_MD5


def test_model01_fixture_matches_validator_original():
    if not ORIGINAL.exists():
        pytest.skip(f"{ORIGINAL} not available")
    assert _md5(FIXTURE) == _md5(ORIGINAL)
