from .. import known
from .bytecode import Dump, Proto


def _constant(k: tuple) -> tuple:
    if k[0] == "child":
        return ("child",)
    if k[0] == "tab":
        return ("tab", repr(k[1:]))
    return k


def signature(fn: Proto) -> tuple:
    operands = tuple(ins.raw >> 8 for ins in fn.code)
    constants = tuple(_constant(k) for k in fn.kgc)
    return operands, constants, tuple(fn.kn), tuple(fn.uv), fn.numparams, fn.framesize


def align(game: list[Dump], stock: list[Dump]) -> tuple[dict[int, int], int]:
    return known.align(game, stock, signature)
