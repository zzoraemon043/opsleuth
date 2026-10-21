from .. import known
from .chunk import Chunk, Function


def signature(fn: Function) -> tuple:
    constants = tuple((k.type, k.value) for k in fn.constants)
    operands = tuple(ins.raw >> 6 for ins in fn.code)
    return len(fn.code), constants, operands, len(fn.protos), fn.nups, fn.num_params


def align(game_chunks: list[Chunk], stock_chunks: list[Chunk]) -> tuple[dict[int, int], int]:
    return known.align(game_chunks, stock_chunks, signature)
