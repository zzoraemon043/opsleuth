from pathlib import Path

import pytest

from opsleuth.lua51.chunk import parse

DATA = Path(__file__).parent / "data"
FIXTURES = sorted((DATA / "luac51").glob("*.luac"))


@pytest.fixture
def fixture_files() -> list[Path]:
    return FIXTURES


@pytest.fixture
def chunks():
    return [parse(f.read_bytes()) for f in FIXTURES]
