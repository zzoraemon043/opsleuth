import shutil
import subprocess

import pytest

from opsleuth.lua51.opcodes import NAMES
from opsleuth.native import find_opname_tables

from .conftest import DATA

SOURCE = DATA / "native" / "vm_table.c"
EXPECTED = (DATA / "native" / "expected.txt").read_text().split()


def _compile(tmp_path, *flags):
    cc = shutil.which("cc") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler")
    out = tmp_path / "vm_table.bin"
    result = subprocess.run([cc, "-O2", *flags, "-o", str(out), str(SOURCE)], capture_output=True)
    if result.returncode != 0:
        pytest.skip(f"compiler rejected flags {flags}")
    return out.read_bytes()


@pytest.mark.parametrize("flags", [(), ("-shared", "-fPIC")])
def test_finds_renumbered_table(tmp_path, flags):
    data = _compile(tmp_path, *flags)
    tables = find_opname_tables(data, set(NAMES))
    assert [t.names for t in tables] == [EXPECTED]


def test_ignores_short_tables():
    blob = b"\0MOVE\0JMP\0" + b"\0" * 64
    assert find_opname_tables(blob, set(NAMES)) == []
