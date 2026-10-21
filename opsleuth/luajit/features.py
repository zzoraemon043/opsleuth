from ..lua51.features import _number_bucket
from .bytecode import Proto
from .opcodes import CALL, CALLM, ITERC, ITERN, JMP, KNIL, KPRI, KSHORT, MODES, NAMES, VARG, is_ad

FAMILIES = ("a", "b", "c", "d", "num", "value", "shape", "prev", "next", "src", "src2", "use",
            "jump", "after", "target")
_VALUES = frozenset((*range(-2, 11), 12, 16, 24, 32, 60, 64, 100, 128, 255, 256, 360, 1000, 1024,
                     3600, 0.5, 0.25, 0.1, 0.01, 0.001))

_WINDOW = 8
_MULTI = (CALL, CALLM, ITERC, ITERN, VARG)
_LITERALS = (KSHORT, KPRI)


def _num(fn: Proto, x: int) -> str | None:
    if x < len(fn.kn):
        return _number_bucket(float(fn.kn[x]))
    return None


def _kind(fn: Proto, x: int) -> str:
    parts = []
    if x < fn.framesize:
        parts.append("r")
    k = fn.kgc_at(x)
    if k is not None:
        parts.append(k[0][0])
    if x < len(fn.kn):
        parts.append("n")
    if x <= 2:
        parts.append(str(x))
    if x < len(fn.uv):
        parts.append("u")
    return "".join(parts) or "big"


def _writes(op: int, ins, r: int) -> bool:
    if op == KNIL:
        return ins.a <= r <= ins.d
    if op in _MULTI:
        return r >= ins.a if ins.b == 0 else ins.a <= r <= ins.a + ins.b - 2
    return MODES[op][0] == "dst" and ins.a == r


def _reads(op: int, ins, r: int) -> bool:
    ma, mb, mcd = MODES[op]
    if ma == "var" and ins.a == r:
        return True
    if is_ad(op):
        return mcd == "var" and ins.d == r
    if mb == "rbase":
        return ins.b <= r <= ins.c
    return (mb == "var" and ins.b == r) or (mcd == "var" and ins.c == r)


def _source(fn: Proto, pc: int, r: int, known: dict[int, int]) -> str | None:
    for back in range(pc - 1, max(-1, pc - 1 - _WINDOW), -1):
        ins = fn.code[back]
        op = known.get(ins.op)
        if op is None or op == JMP:
            return None
        if _writes(op, ins, r):
            if op in _LITERALS and ins.d < 4:
                return f"{NAMES[op]}{ins.d}"
            return NAMES[op]
    return None


def _use(fn: Proto, pc: int, r: int, known: dict[int, int]) -> str | None:
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


def extract(fn: Proto, pc: int, known: dict[int, int]) -> dict[str, str]:
    ins = fn.code[pc]
    out = {
        "a": _small(ins.a),
        "b": _kind(fn, ins.b),
        "c": _kind(fn, ins.c),
        "d": _kind(fn, ins.d),
        "shape": "".join((
            "=" if ins.a == ins.b else "-",
            "=" if ins.a == ins.c else "-",
            "=" if ins.a == ins.d else "-",
            "z" if ins.b == 0 else "b",
            "<" if ins.b < ins.c else ">",
            "<" if ins.a < ins.d else ">",
        )),
    }
    num = _num(fn, ins.c)
    if num is not None:
        out["num"] = num
        value = fn.kn[ins.c]
        out["value"] = repr(float(value)) if value in _VALUES else num
    if pc > 0 and fn.code[pc - 1].op in known:
        out["prev"] = NAMES[known[fn.code[pc - 1].op]]
    if pc + 1 < len(fn.code):
        nxt = fn.code[pc + 1]
        if nxt.op in known:
            out["next"] = NAMES[known[nxt.op]]
            if known[nxt.op] == JMP:
                out["jump"] = "back" if nxt.j < 0 else _small(nxt.j)
                target = pc + 2 + nxt.j
                if 0 <= target < len(fn.code) and fn.code[target].op in known:
                    out["target"] = NAMES[known[fn.code[target].op]]
                if pc + 2 < len(fn.code) and fn.code[pc + 2].op in known:
                    after = fn.code[pc + 2]
                    out["after"] = NAMES[known[after.op]] + str(after.d if after.d < 3 else "")
    src = _source(fn, pc, ins.d if ins.d < fn.framesize else ins.b, known)
    if src:
        out["src"] = src
    if ins.c < fn.framesize:
        src2 = _source(fn, pc, ins.c, known)
        if src2:
            out["src2"] = src2
    use = _use(fn, pc, ins.a, known)
    if use:
        out["use"] = use
    return out
