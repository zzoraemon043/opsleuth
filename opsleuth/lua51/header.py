from dataclasses import dataclass, field
from itertools import product

from .chunk import SIGNATURE, VERSION, Chunk, ChunkError, Header, parse, read_header


@dataclass
class Detection:
    chunk: Chunk
    header: Header
    offset: int
    repairs: list[str] = field(default_factory=list)


def _candidates(original: Header | None):
    for little, size_t, number in product((True, False), (4, 8), (8, 4)):
        yield Header(
            little_endian=little, sizeof_size_t=size_t, sizeof_number=number,
        )
    if original is not None:
        yield Header(
            little_endian=original.little_endian,
            sizeof_size_t=original.sizeof_size_t,
            sizeof_number=original.sizeof_number,
            integral=True,
        )


def _describe(original: Header, used: Header) -> list[str]:
    repairs = []
    if original.signature != SIGNATURE:
        repairs.append(f"signature {original.signature.hex()} -> {SIGNATURE.hex()}")
    if original.version != VERSION:
        repairs.append(f"version 0x{original.version:02x} -> 0x{VERSION:02x}")
    if original.format != 0:
        repairs.append(f"format {original.format} -> 0")
    pairs = (
        ("endianness", int(original.little_endian), int(used.little_endian)),
        ("sizeof(int)", original.sizeof_int, used.sizeof_int),
        ("sizeof(size_t)", original.sizeof_size_t, used.sizeof_size_t),
        ("sizeof(Instruction)", original.sizeof_instruction, used.sizeof_instruction),
        ("sizeof(lua_Number)", original.sizeof_number, used.sizeof_number),
        ("integral flag", int(original.integral), int(used.integral)),
    )
    for name, old, new in pairs:
        if old != new:
            repairs.append(f"{name} {old} -> {new}")
    return repairs


def detect(data: bytes) -> Detection:
    original = read_header(data) if len(data) >= 12 else None
    if original is not None and original.is_standard():
        try:
            return Detection(parse(data, original), original, 12)
        except ChunkError:
            pass
    tried = []
    if original is not None:
        tried.append(original)
    tried.extend(_candidates(original))
    for offset in (12, 0):
        for header in tried:
            try:
                chunk = parse(data, header, offset)
            except (ChunkError, KeyError, OverflowError):
                continue
            if offset == 0:
                repairs = ["header missing -> standard header added"]
            else:
                repairs = _describe(original, header)
            chunk.header = header
            return Detection(chunk, header, offset, repairs)
    raise ChunkError("not a Lua 5.1 chunk under any supported header layout")
