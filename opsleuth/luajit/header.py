from dataclasses import dataclass, field

from .bytecode import (
    F_BE,
    F_STRIP,
    MAGIC,
    BytecodeError,
    Dump,
    Header,
    _Reader,
    parse_body,
)

_KNOWN_FLAGS = 0x1F


@dataclass
class Detection:
    dump: Dump
    header: Header
    offset: int
    repairs: list[str] = field(default_factory=list)


def _read_header(data: bytes) -> tuple[Header, int] | None:
    try:
        r = _Reader(data, 3)
        version = r.byte()
        flags = r.uleb()
        if flags & ~_KNOWN_FLAGS or version != 2:
            return None
        name = r.bytes(r.uleb()) if not flags & F_STRIP else None
    except BytecodeError:
        return None
    return Header(version, flags, name), r.pos


def _try(data: bytes, header: Header, pos: int) -> Dump | None:
    try:
        return parse_body(data, header, pos)
    except (BytecodeError, IndexError, OverflowError):
        return None


def detect(data: bytes) -> Detection:
    if len(data) < 5:
        raise BytecodeError("too short for LuaJIT bytecode")
    read = _read_header(data)
    if read is not None:
        header, pos = read
        d = _try(data, header, pos)
        if d is not None:
            repairs = []
            if data[:3] != MAGIC:
                repairs.append(f"signature {data[:3].hex()} -> {MAGIC.hex()}")
            return Detection(d, header, pos, repairs)
    for flags in (F_STRIP, 0, F_STRIP | F_BE, F_BE):
        header = Header(2, flags, b"?" if not flags & F_STRIP else None)
        d = _try(data, header, 0)
        if d is not None:
            return Detection(d, header, 0, ["header missing -> standard header added"])
    raise BytecodeError("not LuaJIT bytecode under any supported header layout")
