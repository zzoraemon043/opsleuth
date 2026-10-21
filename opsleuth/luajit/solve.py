from .. import solver
from ..solver import Contradiction, Solution
from . import rules
from .bytecode import F_BITOP, F_FFI, Dump
from .features import extract
from .model import Model
from .opcodes import BITOPS, CALLMT, CALLT, DUMPED, KCDATA, NAMES, RETURNS

__all__ = ["DIALECT", "Contradiction", "Solution", "solve"]

DIALECT = solver.Dialect(
    names=NAMES,
    candidates=DUMPED,
    last_ops=frozenset((*RETURNS, CALLT, CALLMT)),
    valid=rules.valid,
    requirements=rules.requirements,
    soft_penalty=rules.soft_penalty,
    extract=extract,
    model=Model,
)


def candidates(dumps: list[Dump]) -> tuple[int, ...]:
    flags = 0
    for d in dumps:
        flags |= d.header.flags
    excluded = set()
    if not flags & F_BITOP:
        excluded.update(BITOPS)
    if not flags & F_FFI:
        excluded.add(KCDATA)
    return tuple(op for op in DUMPED if op not in excluded)


def solve(dumps: list[Dump], model: Model | None = None,
          fixed: dict[int, int] | None = None) -> Solution:
    return solver.solve(dumps, DIALECT, model, fixed, candidates(dumps))
