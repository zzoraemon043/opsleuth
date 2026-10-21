import random

from .bytecode import F_STRIP, Dump, _uleb, dump
from .opcodes import DUMPED


def random_permutation(seed: int | None = None, spread: bool = True) -> dict[int, int]:
    rng = random.Random(seed)
    pool = list(range(256 if spread else len(DUMPED)))
    rng.shuffle(pool)
    return {std: pool[i] for i, std in enumerate(DUMPED)}


def remap(d: Dump, mapping: dict[int, int]) -> None:
    for proto in d.protos:
        proto.code = [ins.with_op(mapping.get(ins.op, ins.op)) for ins in proto.code]


def strip(d: Dump) -> None:
    d.header.flags |= F_STRIP
    d.header.chunkname = None
    for proto in d.protos:
        if proto.debug:
            proto.suffix = proto.suffix[:len(proto.suffix) - len(proto.debug)]
            proto.debug = b""
        proto.prefix = (
            bytes((proto.flags, proto.numparams, proto.framesize, len(proto.uv)))
            + _uleb(len(proto.kgc)) + _uleb(len(proto.kn)) + _uleb(len(proto.code))
        )


def scramble(d: Dump, mapping: dict[int, int], *, strip_debug: bool = False,
             damage_header: bool = False, seed: int | None = None) -> bytes:
    remap(d, mapping)
    if strip_debug:
        strip(d)
    data = dump(d)
    if damage_header:
        rng = random.Random(seed)
        data = bytes(rng.randrange(256) for _ in range(3)) + data[3:]
    return data
