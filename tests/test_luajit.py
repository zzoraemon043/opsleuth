import json

import pytest

from opsleuth.cli import main
from opsleuth.luajit.bytecode import F_FR2, F_STRIP, dump, parse
from opsleuth.luajit.header import detect
from opsleuth.luajit.known import align
from opsleuth.luajit.opcodes import NAMES, OP
from opsleuth.luajit.scramble import random_permutation, remap, strip
from opsleuth.luajit.solve import Contradiction, solve
from opsleuth.luajit.verify import verify

from .conftest import DATA

FIXTURES = sorted((DATA / "luajit").glob("*.ljbc"))


def _scrambled(seed: int):
    perm = random_permutation(seed)
    dumps = []
    for path in FIXTURES:
        d = parse(path.read_bytes())
        remap(d, perm)
        dumps.append(d)
    return dumps, {g: s for s, g in perm.items()}


def test_fixtures_round_trip():
    assert FIXTURES
    for path in FIXTURES:
        data = path.read_bytes()
        d = parse(data)
        assert dump(d) == data
        assert d.header.flags & F_FR2
        assert verify(d).ok


def test_strip_keeps_code_and_drops_debug_info():
    for path in FIXTURES:
        d = parse(path.read_bytes())
        code = [p.code for p in d.protos]
        strip(d)
        data = dump(d)
        again = parse(data)
        assert again.header.flags & F_STRIP
        assert [p.code for p in again.protos] == code
        assert len(data) < path.stat().st_size


def test_header_repairs():
    data = FIXTURES[0].read_bytes()
    assert detect(data).repairs == []
    changed = detect(b"ABC" + data[3:])
    assert changed.repairs and dump(changed.dump, changed.header)[3:] == data[3:]
    d = parse(data)
    strip(d)
    stripped = dump(d)
    missing = detect(stripped[5:])
    assert missing.repairs == ["header missing -> standard header added"]
    assert [p.code for p in missing.dump.protos] == [p.code for p in d.protos]


@pytest.mark.parametrize("seed", range(4))
def test_solve_only_errs_on_flagged_opcodes(seed):
    dumps, truth = _scrambled(seed)
    solution = solve(dumps)
    flagged = {r.game for r in solution.ambiguous()}
    wrong = {g for g, s in solution.mapping.items() if truth[g] != s}
    assert wrong <= flagged
    assert len(wrong) <= len(solution.ops) // 10
    for name in ("JMP", "CALL", "RET0", "FORI", "FORL", "ITERC", "ITERL", "TGETS", "GGET"):
        game = next(g for g, s in truth.items() if s == OP[name])
        assert solution.mapping[game] == OP[name]


def test_fixed_mapping_is_checked():
    dumps, truth = _scrambled(1)
    solution = solve(dumps, fixed=truth)
    assert solution.mapping == {g: truth[g] for g in solution.ops}
    assert all(r.method == "given" for r in solution.ops.values())
    wrong = dict(truth)
    a, b = (g for g, s in truth.items() if NAMES[s] in ("JMP", "CALL"))
    wrong[a], wrong[b] = wrong[b], wrong[a]
    with pytest.raises(Contradiction):
        solve(dumps, fixed=wrong)


def test_known_bytecode_alignment():
    dumps, truth = _scrambled(2)
    stock = [parse(p.read_bytes()) for p in FIXTURES[:3]]
    mapping, matched = align(dumps, stock)
    assert matched > 0
    assert mapping and all(truth[g] == s for g, s in mapping.items())


def test_cli_pipeline(tmp_path):
    game = tmp_path / "game"
    answer = tmp_path / "answer.json"
    mapping = tmp_path / "map.json"
    fixed = tmp_path / "fixed"
    restored = tmp_path / "restored"
    plain = DATA / "luajit"

    assert main(["scramble", str(plain), "-o", str(game), "--seed", "3", "--strip",
                 "--damage-header", "--answer", str(answer)]) == 0
    assert main(["verify", str(game)]) == 1
    assert main(["detect", str(game)]) == 0
    assert main(["solve", str(game), "-o", str(mapping)]) == 0
    data = json.loads(mapping.read_text())
    assert data["lua"] == "luajit2.1"
    truth = {o["game"]: o["op"] for o in json.loads(answer.read_text())["ops"]}
    wrong = {o["game"] for o in data["ops"] if truth[o["game"]] != o["op"]}
    assert wrong <= set(data["ambiguous"])

    assert main(["apply", str(game), "--map", str(mapping), "-o", str(fixed)]) == 0
    assert main(["verify", str(fixed)]) == 0
    assert main(["apply", str(game), "--map", str(answer), "-o", str(restored)]) == 0
    for original in FIXTURES:
        d = parse(original.read_bytes())
        strip(d)
        assert (restored / original.name).read_bytes() == dump(d)
