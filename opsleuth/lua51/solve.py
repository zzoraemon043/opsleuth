from .. import solver
from ..solver import Contradiction, Solution
from . import rules
from .features import extract
from .model import Model
from .opcodes import NAMES, NUM_OPCODES, RETURN

__all__ = ["DIALECT", "Contradiction", "Solution", "solve"]

DIALECT = solver.Dialect(
    names=NAMES,
    candidates=tuple(range(NUM_OPCODES)),
    last_ops=frozenset((RETURN,)),
    valid=rules.valid,
    requirements=rules.requirements,
    soft_penalty=rules.soft_penalty,
    extract=extract,
    model=Model,
)


def solve(chunks, model: Model | None = None, fixed: dict[int, int] | None = None) -> Solution:
    return solver.solve(chunks, DIALECT, model, fixed)
