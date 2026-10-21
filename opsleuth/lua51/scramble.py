import random

from .chunk import Chunk, Header, dump
from .opcodes import NUM_OPCODES


def random_permutation(seed: int | None = None, spread: bool = True) -> dict[int, int]:
    rng = random.Random(seed)
    pool = list(range(64 if spread else NUM_OPCODES))
    rng.shuffle(pool)
    return {std: pool[std] for std in range(NUM_OPCODES)}


def remap(chunk: Chunk, mapping: dict[int, int]) -> None:
    for fn in chunk.functions():
        fn.code = [ins.with_op(mapping.get(ins.op, ins.op)) for ins in fn.code]


def strip(chunk: Chunk) -> None:
    for fn in chunk.functions():
        fn.source = None
        fn.line_info = []
        fn.loc_vars = []
        fn.upvalue_names = []


def damaged_header(header: Header, rng: random.Random) -> bytes:
    raw = bytearray(header.encode())
    choice = rng.randrange(4)
    if choice == 0:
        raw[0:4] = bytes(rng.randrange(256) for _ in range(4))
    elif choice == 1:
        raw[4] = rng.choice((0x00, 0x52, 0x99))
    elif choice == 2:
        raw[8] = 0
    else:
        raw[7:11] = b"\0\0\0\0"
    return bytes(raw)


def scramble(chunk: Chunk, mapping: dict[int, int], *, strip_debug: bool = False,
             damage_header: bool = False, seed: int | None = None) -> bytes:
    remap(chunk, mapping)
    if strip_debug:
        strip(chunk)
    data = dump(chunk)
    if damage_header:
        data = damaged_header(chunk.header, random.Random(seed)) + data[12:]
    return data
