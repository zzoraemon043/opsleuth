import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from opsleuth.cli import main
from opsleuth.lua51.chunk import dump, parse
from opsleuth.lua51.opcodes import OP
from opsleuth.lua51.scramble import remap

from .conftest import DATA


def test_full_pipeline(tmp_path):
    plain = DATA / "luac51"
    game = tmp_path / "game"
    answer = tmp_path / "answer.json"
    mapping = tmp_path / "map.json"
    fixed = tmp_path / "fixed"

    assert main(["scramble", str(plain), "-o", str(game), "--seed", "11", "--strip",
                 "--damage-header", "--answer", str(answer)]) == 0
    assert main(["verify", str(game)]) == 1
    assert main(["detect", str(game)]) == 0
    assert main(["solve", str(game), "-o", str(mapping)]) == 0

    truth = {o["game"]: o["op"] for o in json.loads(answer.read_text())["ops"]}
    found = {o["game"]: o["op"] for o in json.loads(mapping.read_text())["ops"]}
    assert found == truth

    assert main(["apply", str(game), "--map", str(mapping), "-o", str(fixed)]) == 0
    assert main(["verify", str(fixed)]) == 0
    for original in plain.glob("*.luac"):
        restored = (fixed / original.name).read_bytes()
        assert len(restored) < len(original.read_bytes())


def test_solve_reports_no_input(tmp_path):
    (tmp_path / "notes.txt").write_text("not bytecode")
    assert main(["solve", str(tmp_path)]) == 1


def test_native_table_shortcut(tmp_path):
    cc = shutil.which("cc") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler")
    binary = tmp_path / "vm.bin"
    subprocess.run([cc, "-O2", "-o", str(binary), str(DATA / "native" / "vm_table.c")], check=True)
    order = (DATA / "native" / "expected.txt").read_text().split()
    perm = {OP[name]: i for i, name in enumerate(order)}
    game = tmp_path / "game"
    game.mkdir()
    for src in (DATA / "luac51").glob("*.luac"):
        chunk = parse(src.read_bytes())
        remap(chunk, perm)
        (game / src.name).write_bytes(dump(chunk))
    mapping = tmp_path / "map.json"
    assert main(["solve", str(game), "--lib", str(binary), "-o", str(mapping)]) == 0
    ops = json.loads(mapping.read_text())["ops"]
    assert all(o["method"] == "native" for o in ops)
    assert all(order[o["game"]] == o["op"] for o in ops)


def test_known_bytecode_fixes_opcodes(tmp_path):
    plain = DATA / "luac51"
    game = tmp_path / "game"
    known = tmp_path / "known"
    known.mkdir()
    for name in ("stats.luac", "geometry.luac"):
        (known / name).write_bytes((plain / name).read_bytes())
    mapping = tmp_path / "map.json"
    answer = tmp_path / "answer.json"
    assert main(["scramble", str(plain), "-o", str(game), "--seed", "4", "--answer", str(answer)]) == 0
    assert main(["solve", str(game), "--known", str(known), "-o", str(mapping)]) == 0
    truth = {o["game"]: o["op"] for o in json.loads(answer.read_text())["ops"]}
    ops = json.loads(mapping.read_text())["ops"]
    assert {o["game"]: o["op"] for o in ops} == {g: truth[g] for g in (o["game"] for o in ops)}
    known_ops = {o["op"] for o in ops if o["method"] == "known"}
    assert {"POW", "MOD", "DIV", "MUL", "UNM"} <= known_ops


def test_verify_runs_a_decompiler_command(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text("import sys\nopen(sys.argv[1], 'rb').read()\n")
    fail = tmp_path / "fail.py"
    fail.write_text("import sys\nsys.exit('cannot decompile')\n")
    python = shlex.quote(Path(sys.executable).as_posix())
    for folder in (DATA / "luac51", DATA / "luajit"):
        assert main(["verify", str(folder), "--decompiler", f"{python} {ok.as_posix()} {{}}"]) == 0
        assert main(["verify", str(folder), "--decompiler", f"{python} {fail.as_posix()}"]) == 1
