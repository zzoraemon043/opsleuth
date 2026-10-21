from .chunk import BOOLEAN, NIL, NUMBER, STRING, Function
from .opcodes import (
    CALL,
    FORLOOP,
    FORPREP,
    JMP,
    LOADNIL,
    NAMES,
    RETURN,
    SETGLOBAL,
    SETLIST,
    SETTABLE,
    SETUPVAL,
    TAILCALL,
    TEST,
    TFORLOOP,
    constant_index,
    is_constant,
)

FAMILIES = ("b", "c", "a", "shape", "prev", "next", "src", "use")

_R, _K, _U, _N = "R", "K", "U", "N"
_MODES = (
    (1, _R, _N), (1, _K, _N), (1, _U, _U), (1, _R, _N), (1, _U, _N), (1, _K, _N),
    (1, _R, _K), (0, _K, _N), (0, _U, _N), (0, _K, _K), (1, _U, _U), (1, _R, _K),
    (1, _K, _K), (1, _K, _K), (1, _K, _K), (1, _K, _K), (1, _K, _K), (1, _K, _K),
    (1, _R, _N), (1, _R, _N), (1, _R, _N), (1, _R, _R), (0, _R, _N), (0, _K, _K),
    (0, _K, _K), (0, _K, _K), (0, _R, _U), (1, _R, _U), (1, _U, _U), (1, _U, _U),
    (0, _U, _N), (1, _R, _N), (1, _R, _N), (0, _N, _U), (0, _U, _U), (0, _N, _N),
    (1, _U, _N), (1, _U, _N),
)
_READS_A = {SETGLOBAL, SETUPVAL, SETTABLE, TEST, CALL, TAILCALL, RETURN, FORPREP,
            FORLOOP, TFORLOOP, SETLIST}
_WINDOW = 8


def _number_bucket(x: float) -> str:
    if x != x or x in (float("inf"), float("-inf")):
        return "nan"
    if x == int(x):
        i = int(x)
        if i in (-1, 0, 1, 2):
            return str(i)
        if 0 < i <= 10:
            return "small"
        if i in (16, 32, 60, 100, 255, 256, 1000, 1024):
            return "round"
        return "int"
    if x in (0.5, 0.25):
        return "frac"
    return "float"


def _rk_kind(fn: Function, x: int) -> str:
    if not is_constant(x):
        return "r"
    i = constant_index(x)
    if i >= len(fn.constants):
        return "k?"
    k = fn.constants[i]
    if k.type == NUMBER:
        return "n" + _number_bucket(k.value)
    if k.type == STRING:
        return "s"
    if k.type == NIL:
        return "nil"
    if k.type == BOOLEAN:
        return "bool"
    return "k?"


def _writes(op: int, ins, r: int) -> bool:
    if not _MODES[op][0]:
        return False
    if op == LOADNIL:
        return ins.a <= r <= ins.b
    if op == CALL:
        return r >= ins.a if ins.c == 0 else ins.a <= r <= ins.a + ins.c - 2
    return ins.a == r


def _reads(op: int, ins, r: int) -> bool:
    _, bm, cm = _MODES[op]
    if bm in (_R, _K) and ins.b == r:
        return True
    if cm in (_R, _K) and ins.c == r:
        return True
    return op in _READS_A and ins.a == r


def _source(fn: Function, pc: int, r: int, known: dict[int, int]) -> str | None:
    for back in range(pc - 1, max(-1, pc - 1 - _WINDOW), -1):
        op = known.get(fn.code[back].op)
        if op is None or op == JMP:
            return None
        if _writes(op, fn.code[back], r):
            return NAMES[op]
    return None


def _use(fn: Function, pc: int, r: int, known: dict[int, int]) -> str | None:
    for fwd in range(pc + 1, min(len(fn.code), pc + 1 + _WINDOW)):
        op = known.get(fn.code[fwd].op)
        if op is None:
            return None
        ins = fn.code[fwd]
        if _reads(op, ins, r):
            return NAMES[op]
        if _writes(op, ins, r) or op == JMP:
            return None
    return None


def _small(x: int) -> str:
    return str(x) if x < 4 else "many"


def extract(fn: Function, pc: int, known: dict[int, int]) -> dict[str, str]:
    ins = fn.code[pc]
    out = {
        "b": _rk_kind(fn, ins.b),
        "c": _rk_kind(fn, ins.c),
        "a": _small(ins.a),
        "shape": "".join((
            "=" if ins.a == ins.b else "-",
            "z" if ins.b == 0 else "b",
            "z" if ins.c == 0 else "c",
            "<" if ins.b < ins.c else ">",
        )),
    }
    if pc > 0 and fn.code[pc - 1].op in known:
        out["prev"] = NAMES[known[fn.code[pc - 1].op]]
    if pc + 1 < len(fn.code) and fn.code[pc + 1].op in known:
        out["next"] = NAMES[known[fn.code[pc + 1].op]]
    if not is_constant(ins.b):
        src = _source(fn, pc, ins.b, known)
        if src:
            out["src"] = src
    use = _use(fn, pc, ins.a, known)
    if use:
        out["use"] = use
    return out
