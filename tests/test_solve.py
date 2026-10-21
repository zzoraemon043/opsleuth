import pytest

from opsleuth.assign import INF, min_cost_assignment
from opsleuth.lua51.chunk import parse
from opsleuth.lua51.opcodes import NAMES, RETURN
from opsleuth.lua51.scramble import random_permutation, remap, strip
from opsleuth.lua51.solve import Contradiction, solve


def _scrambled(fixture_files, seed, stripped=False):
    perm = random_permutation(seed)
    chunks = []
    for path in fixture_files:
        chunk = parse(path.read_bytes())
        remap(chunk, perm)
        if stripped:
            strip(chunk)
        chunks.append(chunk)
    return chunks, {g: s for s, g in perm.items()}


@pytest.mark.parametrize("seed", range(6))
def test_solve_recovers_every_opcode(fixture_files, seed):
    chunks, truth = _scrambled(fixture_files, seed, stripped=seed % 2 == 1)
    solution = solve(chunks)
    wrong = {NAMES[truth[g]]: NAMES[s] for g, s in solution.mapping.items() if truth[g] != s}
    assert wrong == {}
    assert len(solution.mapping) == len(NAMES)


def test_return_is_forced_by_structure(fixture_files):
    chunks, truth = _scrambled(fixture_files, 3)
    solution = solve(chunks)
    returns = [r for r in solution.ops.values() if r.op == RETURN]
    assert len(returns) == 1
    assert returns[0].method == "constraint"
    assert truth[returns[0].game] == RETURN


def test_fixed_mapping_is_used(fixture_files):
    chunks, truth = _scrambled(fixture_files, 4)
    solution = solve(chunks, fixed=truth)
    assert solution.mapping == truth
    assert all(r.method == "given" for r in solution.ops.values())


def test_inconsistent_fixed_mapping_is_rejected(fixture_files):
    chunks, truth = _scrambled(fixture_files, 5)
    wrong = dict(truth)
    a, b = [g for g, s in truth.items() if NAMES[s] in ("JMP", "CALL")]
    wrong[a], wrong[b] = wrong[b], wrong[a]
    with pytest.raises(Contradiction):
        solve(chunks, fixed=wrong)


def test_assignment_prefers_lowest_cost():
    cost = [[4, 1, 3], [2, 0, 5], [3, 2, 2]]
    assert min_cost_assignment(cost) == [1, 0, 2]


def test_assignment_respects_forbidden_cells():
    cost = [[INF, 1], [1, INF]]
    assert min_cost_assignment(cost) == [1, 0]
