from .bytecode import Proto
from .opcodes import (
    BITOPS,
    CALL,
    CALLM,
    CALLMT,
    CALLT,
    CAT,
    COMPARE,
    FORI,
    FORL,
    ISNEXT,
    ITERC,
    ITERL,
    ITERN,
    JMP,
    KCDATA,
    KNIL,
    LOOP,
    MODES,
    MULTRES,
    RET,
    RET0,
    RET1,
    RETM,
    RETURNS,
    TESTS,
    TSETM,
    UCLO,
    VARG,
)

_CDATA = ("i64", "u64", "complex")
_MULTRES_SOURCES = frozenset((CALL, CALLM, VARG))


def _operand(mode: str, fn: Proto, x: int, pc: int) -> bool:
    if mode in ("dst", "var", "base"):
        return x < fn.framesize
    if mode == "rbase":
        return x <= fn.framesize
    if mode == "str":
        k = fn.kgc_at(x)
        return k is not None and k[0] == "str"
    if mode == "num":
        return x < len(fn.kn)
    if mode == "pri":
        return x <= 2
    if mode == "uv":
        return x < len(fn.uv)
    if mode == "func":
        k = fn.kgc_at(x)
        return k is not None and k[0] == "child"
    if mode == "tab":
        k = fn.kgc_at(x)
        return k is not None and k[0] == "tab"
    if mode == "cdata":
        k = fn.kgc_at(x)
        return k is not None and k[0] in _CDATA
    if mode == "jump":
        return 0 <= pc + 1 + x - 0x8000 <= len(fn.code)
    return True


def valid(op: int, fn: Proto, pc: int) -> bool:
    if op in BITOPS and not fn.uses_bitops or op == KCDATA and not fn.uses_ffi:
        return False
    ins = fn.code[pc]
    ma, mb, mcd = MODES[op]
    if ma == "___":
        if ins.a != 0:
            return False
    elif not _operand(ma, fn, ins.a, pc):
        return False
    if mb == "___":
        if not _operand(mcd, fn, ins.d, pc):
            return False
    elif not (_operand(mb, fn, ins.b, pc) and _operand(mcd, fn, ins.c, pc)):
        return False
    if op in COMPARE or op in TESTS:
        return pc + 1 < len(fn.code)
    if op in (ITERC, ITERN):
        return ins.c == 3 and _pairs_back(fn, pc + 1, ins.a) and fn.code[pc + 1].j < 0
    if op == RET0:
        return ins.d == 1
    if op == RET1:
        return ins.d == 2 and ins.a < fn.framesize
    if op == RET:
        return ins.d != 2 and ins.d != 1 and ins.a + ins.d - 1 <= fn.framesize
    if op == KNIL:
        return ins.a <= ins.d
    if op == CAT:
        return ins.b < ins.c
    if op == VARG:
        return fn.is_vararg and ins.c == fn.numparams
    if op in MULTRES:
        return pc > 0
    if op == FORI:
        target = pc + 1 + ins.j
        return (ins.j > 0 and ins.a + 3 < fn.framesize
                and _jumps_to(fn, target - 1, ins.a, pc + 1))
    if op == FORL:
        return (ins.j < 0 and ins.a + 3 < fn.framesize
                and _jumps_to(fn, pc + ins.j, ins.a, pc + 1))
    if op == ITERL:
        target = pc + 1 + ins.j
        return (ins.j < 0 and ins.a >= 3 and _pairs_back(fn, pc - 1, ins.a)
                and _jumps_to(fn, target - 1, None, pc - 1))
    if op == LOOP:
        return ins.j >= -1
    if op == ISNEXT:
        target = pc + 1 + ins.j
        return (ins.j >= 0 and _pairs_back(fn, target, ins.a)
                and _jumps_to(fn, target + 1, ins.a, pc + 1))
    return True


def _pairs_back(fn: Proto, pc: int, a: int) -> bool:
    return 0 <= pc < len(fn.code) and fn.code[pc].a == a


def _jumps_to(fn: Proto, pc: int, a: int | None, target: int) -> bool:
    if not 0 <= pc < len(fn.code):
        return False
    other = fn.code[pc]
    return (a is None or other.a == a) and pc + 1 + other.j == target


def requirements(op: int, fn: Proto, pc: int):
    ins = fn.code[pc]
    if op in COMPARE or op in TESTS:
        yield pc + 1, frozenset((JMP,))
    elif op in (ITERC, ITERN):
        yield pc + 1, frozenset((ITERL,))
    elif op == ITERL:
        yield pc - 1, frozenset((ITERC, ITERN))
        yield pc + ins.j, frozenset((JMP, ISNEXT))
    elif op == ISNEXT:
        yield pc + 1 + ins.j, frozenset((ITERN,))
    elif op == FORI:
        yield pc + ins.j, frozenset((FORL,))
    elif op == FORL:
        yield pc + ins.j, frozenset((FORI,))
    elif op in (CALLM, TSETM):
        yield pc - 1, _MULTRES_SOURCES
    elif op in (CALLMT, RETM):
        yield pc - 1, _MULTRES_SOURCES | frozenset((UCLO, CALLT, CALLMT, *RETURNS))


def soft_penalty(op: int, fn: Proto, pc: int) -> bool:
    return False
