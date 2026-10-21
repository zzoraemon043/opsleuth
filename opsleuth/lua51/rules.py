from .chunk import NUMBER, STRING, Function
from .opcodes import (
    ARITH,
    CALL,
    CLOSE,
    CLOSURE,
    COMPARE,
    CONCAT,
    DIV,
    EQ,
    FORLOOP,
    FORPREP,
    GETGLOBAL,
    GETTABLE,
    GETUPVAL,
    JMP,
    LE,
    LEN,
    LOADBOOL,
    LOADK,
    LOADNIL,
    LT,
    MOD,
    MOVE,
    NEWTABLE,
    NOT,
    RETURN,
    SELF,
    SETGLOBAL,
    SETLIST,
    SETTABLE,
    SETUPVAL,
    TAILCALL,
    TEST,
    TESTSET,
    TFORLOOP,
    UNM,
    VARARG,
    Instruction,
    constant_index,
    is_constant,
)

VARARG_ISVARARG = 2
TO_JMP = (EQ, LT, LE, TEST, TESTSET, TFORLOOP)


def _reg(fn: Function, r: int) -> bool:
    return r < fn.max_stack


def _rk(fn: Function, x: int) -> bool:
    if is_constant(x):
        return constant_index(x) < len(fn.constants)
    return x < fn.max_stack


def _kstring(fn: Function, i: int) -> bool:
    return i < len(fn.constants) and fn.constants[i].type == STRING


def _jump_ok(fn: Function, pc: int, ins: Instruction) -> bool:
    return 0 <= pc + 1 + ins.sbx < len(fn.code)


def _results_ok(fn: Function, a: int, count: int) -> bool:
    return count == 0 or a + count - 1 <= fn.max_stack


def valid(op: int, fn: Function, pc: int) -> bool:
    ins = fn.code[pc]
    a, b, c = ins.a, ins.b, ins.c
    if op == MOVE:
        return _reg(fn, a) and _reg(fn, b) and c == 0
    if op == LOADK:
        return _reg(fn, a) and ins.bx < len(fn.constants)
    if op == LOADBOOL:
        return _reg(fn, a) and b <= 1 and c <= 1
    if op == LOADNIL:
        return _reg(fn, a) and _reg(fn, b) and b >= a and c == 0
    if op in (GETUPVAL, SETUPVAL):
        return _reg(fn, a) and b < fn.nups and c == 0
    if op in (GETGLOBAL, SETGLOBAL):
        return _reg(fn, a) and _kstring(fn, ins.bx)
    if op == GETTABLE:
        return _reg(fn, a) and _reg(fn, b) and _rk(fn, c)
    if op == SETTABLE:
        return _reg(fn, a) and _rk(fn, b) and _rk(fn, c)
    if op == NEWTABLE:
        return _reg(fn, a)
    if op == SELF:
        return (
            _reg(fn, a + 1) and _reg(fn, b) and _rk(fn, c)
            and (not is_constant(c) or _kstring(fn, constant_index(c)))
        )
    if op in ARITH:
        return _reg(fn, a) and _rk(fn, b) and _rk(fn, c)
    if op in (UNM, NOT, LEN):
        return _reg(fn, a) and _reg(fn, b) and c == 0
    if op == CONCAT:
        return _reg(fn, a) and _reg(fn, c) and b < c
    if op == JMP:
        return a == 0 and _jump_ok(fn, pc, ins)
    if op in COMPARE:
        return a <= 1 and _rk(fn, b) and _rk(fn, c) and pc + 1 < len(fn.code)
    if op == TEST:
        return _reg(fn, a) and b == 0 and c <= 1 and pc + 1 < len(fn.code)
    if op == TESTSET:
        return _reg(fn, a) and _reg(fn, b) and c <= 1 and pc + 1 < len(fn.code)
    if op == CALL:
        return (
            _reg(fn, a) and _results_ok(fn, a, b)
            and (c < 2 or a + c - 2 < fn.max_stack)
        )
    if op == TAILCALL:
        return _reg(fn, a) and _results_ok(fn, a, b) and c == 0 and pc + 1 < len(fn.code)
    if op == RETURN:
        return a <= fn.max_stack and _results_ok(fn, a, b) and c == 0
    if op == FORLOOP:
        return _reg(fn, a + 3) and ins.sbx < 0 and _jump_ok(fn, pc, ins)
    if op == FORPREP:
        return _reg(fn, a + 3) and ins.sbx >= 0 and _jump_ok(fn, pc, ins)
    if op == TFORLOOP:
        return b == 0 and c >= 1 and _reg(fn, a + 2 + c) and pc + 1 < len(fn.code)
    if op == SETLIST:
        return _reg(fn, a)
    if op == CLOSE:
        return a <= fn.max_stack and b == 0 and c == 0
    if op == CLOSURE:
        if not (_reg(fn, a) and ins.bx < len(fn.protos)):
            return False
        return pc + fn.protos[ins.bx].nups < len(fn.code)
    if op == VARARG:
        return (
            _reg(fn, a) and c == 0 and fn.is_vararg & VARARG_ISVARARG != 0
            and (b < 2 or a + b - 2 < fn.max_stack)
        )
    return False


def requirements(op: int, fn: Function, pc: int):
    ins = fn.code[pc]
    if op in TO_JMP:
        yield pc + 1, frozenset((JMP,))
    elif op == TAILCALL:
        yield pc + 1, frozenset((RETURN,))
    elif op == CLOSURE:
        for k in range(fn.protos[ins.bx].nups):
            yield pc + 1 + k, frozenset((MOVE, GETUPVAL))
    elif op == FORPREP:
        yield pc + 1 + ins.sbx, frozenset((FORLOOP,))
    elif op == FORLOOP:
        yield pc + ins.sbx, frozenset((FORPREP,))


def soft_penalty(op: int, fn: Function, pc: int) -> bool:
    ins = fn.code[pc]
    operands = (ins.b, ins.c)
    if op in ARITH:
        for x in operands:
            if is_constant(x) and fn.constants[constant_index(x)].type != NUMBER:
                return True
        return is_constant(ins.b) and is_constant(ins.c) and op not in (DIV, MOD)
    if op in (LT, LE):
        for x in operands:
            if is_constant(x) and fn.constants[constant_index(x)].type not in (NUMBER, STRING):
                return True
    return False

