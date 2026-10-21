from dataclasses import dataclass

_DEFS = """
ISLT var ___ var
ISGE var ___ var
ISLE var ___ var
ISGT var ___ var
ISEQV var ___ var
ISNEV var ___ var
ISEQS var ___ str
ISNES var ___ str
ISEQN var ___ num
ISNEN var ___ num
ISEQP var ___ pri
ISNEP var ___ pri
ISTC dst ___ var
ISFC dst ___ var
IST ___ ___ var
ISF ___ ___ var
ISTYPE var ___ lit
ISNUM var ___ lit
MOV dst ___ var
NOT dst ___ var
UNM dst ___ var
LEN dst ___ var
ADDVN dst var num
SUBVN dst var num
MULVN dst var num
DIVVN dst var num
MODVN dst var num
ADDNV dst var num
SUBNV dst var num
MULNV dst var num
DIVNV dst var num
MODNV dst var num
ADDVV dst var var
SUBVV dst var var
MULVV dst var var
DIVVV dst var var
MODVV dst var var
POW dst var var
CAT dst rbase rbase
KSTR dst ___ str
KCDATA dst ___ cdata
KSHORT dst ___ lits
KNUM dst ___ num
KPRI dst ___ pri
KNIL base ___ base
UGET dst ___ uv
USETV uv ___ var
USETS uv ___ str
USETN uv ___ num
USETP uv ___ pri
UCLO rbase ___ jump
FNEW dst ___ func
TNEW dst ___ lit
TDUP dst ___ tab
GGET dst ___ str
GSET var ___ str
TGETV dst var var
TGETS dst var str
TGETB dst var lit
TGETR dst var var
TSETV var var var
TSETS var var str
TSETB var var lit
TSETM base ___ num
TSETR var var var
CALLM base lit lit
CALL base lit lit
CALLMT base ___ lit
CALLT base ___ lit
ITERC base lit lit
ITERN base lit lit
VARG base lit lit
ISNEXT base ___ jump
RETM base ___ lit
RET rbase ___ lit
RET0 rbase ___ lit
RET1 rbase ___ lit
FORI base ___ jump
JFORI base ___ jump
FORL base ___ jump
IFORL base ___ jump
JFORL base ___ lit
ITERL base ___ jump
IITERL base ___ jump
JITERL base ___ lit
LOOP rbase ___ jump
ILOOP rbase ___ jump
JLOOP rbase ___ lit
JMP rbase ___ jump
BNOT dst ___ var
BAND dst var var
BOR dst var var
BXOR dst var var
BSHL dst var var
BSHR dst var var
BSAR dst var var
FUNCF rbase ___ ___
IFUNCF rbase ___ ___
JFUNCF rbase ___ lit
FUNCV rbase ___ ___
IFUNCV rbase ___ ___
JFUNCV rbase ___ lit
FUNCC rbase ___ ___
FUNCCW rbase ___ ___
"""

NAMES = tuple(line.split()[0] for line in _DEFS.strip().splitlines())
MODES = tuple(tuple(line.split()[1:]) for line in _DEFS.strip().splitlines())
OP = {name: i for i, name in enumerate(NAMES)}
NUM_OPCODES = len(NAMES)

globals().update(OP)

COMPARE = tuple(OP[n] for n in (
    "ISLT", "ISGE", "ISLE", "ISGT", "ISEQV", "ISNEV", "ISEQS", "ISNES", "ISEQN", "ISNEN",
    "ISEQP", "ISNEP"))
TESTS = tuple(OP[n] for n in ("ISTC", "ISFC", "IST", "ISF"))
ARITH = tuple(range(OP["ADDVN"], OP["POW"] + 1))
BITOPS = tuple(range(OP["BNOT"], OP["BSAR"] + 1))
RETURNS = tuple(OP[n] for n in ("RETM", "RET", "RET0", "RET1"))
MULTRES = tuple(OP[n] for n in ("CALLM", "CALLMT", "RETM", "TSETM"))
NOT_DUMPED = frozenset(OP[n] for n in (
    "ISTYPE", "ISNUM", "TGETR", "TSETR", "JFORI", "IFORL", "JFORL", "IITERL", "JITERL",
    "ILOOP", "JLOOP", "FUNCF", "IFUNCF", "JFUNCF", "FUNCV", "IFUNCV", "JFUNCV", "FUNCC",
    "FUNCCW"))
DUMPED = tuple(op for op in range(NUM_OPCODES) if op not in NOT_DUMPED)

JUMP_BIAS = 0x8000


def is_ad(op: int) -> bool:
    return MODES[op][1] == "___"


@dataclass(frozen=True)
class Instruction:
    raw: int

    @property
    def op(self) -> int:
        return self.raw & 0xFF

    @property
    def a(self) -> int:
        return (self.raw >> 8) & 0xFF

    @property
    def c(self) -> int:
        return (self.raw >> 16) & 0xFF

    @property
    def b(self) -> int:
        return self.raw >> 24

    @property
    def d(self) -> int:
        return self.raw >> 16

    @property
    def j(self) -> int:
        return self.d - JUMP_BIAS

    def with_op(self, op: int) -> "Instruction":
        return Instruction((self.raw & ~0xFF) | (op & 0xFF))
