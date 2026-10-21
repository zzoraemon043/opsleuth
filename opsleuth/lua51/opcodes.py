from dataclasses import dataclass

NAMES = (
    "MOVE", "LOADK", "LOADBOOL", "LOADNIL", "GETUPVAL", "GETGLOBAL",
    "GETTABLE", "SETGLOBAL", "SETUPVAL", "SETTABLE", "NEWTABLE", "SELF",
    "ADD", "SUB", "MUL", "DIV", "MOD", "POW", "UNM", "NOT", "LEN", "CONCAT",
    "JMP", "EQ", "LT", "LE", "TEST", "TESTSET", "CALL", "TAILCALL", "RETURN",
    "FORLOOP", "FORPREP", "TFORLOOP", "SETLIST", "CLOSE", "CLOSURE", "VARARG",
)

OP = {name: i for i, name in enumerate(NAMES)}
NUM_OPCODES = len(NAMES)

MOVE, LOADK, LOADBOOL, LOADNIL, GETUPVAL, GETGLOBAL = range(6)
GETTABLE, SETGLOBAL, SETUPVAL, SETTABLE, NEWTABLE, SELF = range(6, 12)
ADD, SUB, MUL, DIV, MOD, POW, UNM, NOT, LEN, CONCAT = range(12, 22)
JMP, EQ, LT, LE, TEST, TESTSET, CALL, TAILCALL, RETURN = range(22, 31)
FORLOOP, FORPREP, TFORLOOP, SETLIST, CLOSE, CLOSURE, VARARG = range(31, 38)

ARITH = (ADD, SUB, MUL, DIV, MOD, POW)
UNARY = (UNM, NOT, LEN)
COMPARE = (EQ, LT, LE)

SIZE_OP = 6
MAXARG_SBX = (1 << 18) - 1 >> 1
BITRK = 1 << 8


@dataclass(frozen=True)
class Instruction:
    raw: int

    @property
    def op(self) -> int:
        return self.raw & 0x3F

    @property
    def a(self) -> int:
        return (self.raw >> 6) & 0xFF

    @property
    def c(self) -> int:
        return (self.raw >> 14) & 0x1FF

    @property
    def b(self) -> int:
        return (self.raw >> 23) & 0x1FF

    @property
    def bx(self) -> int:
        return (self.raw >> 14) & 0x3FFFF

    @property
    def sbx(self) -> int:
        return self.bx - MAXARG_SBX

    def with_op(self, op: int) -> "Instruction":
        return Instruction((self.raw & ~0x3F) | (op & 0x3F))


def is_constant(rk: int) -> bool:
    return rk & BITRK != 0


def constant_index(rk: int) -> int:
    return rk & ~BITRK
