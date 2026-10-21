from dataclasses import dataclass, field

from .lua51 import opcodes as lua51_opcodes
from .lua51.chunk import ChunkError
from .lua51.chunk import Header as Lua51Header
from .lua51.chunk import dump as lua51_dump
from .lua51.header import detect as lua51_detect
from .lua51.known import align as lua51_align
from .lua51.scramble import random_permutation as lua51_permutation
from .lua51.scramble import scramble as lua51_scramble
from .lua51.solve import solve as lua51_solve
from .lua51.verify import verify as lua51_verify
from .luajit import opcodes as luajit_opcodes
from .luajit.bytecode import MAGIC as LUAJIT_MAGIC
from .luajit.bytecode import BytecodeError
from .luajit.bytecode import Header as LuajitHeader
from .luajit.bytecode import dump as luajit_dump
from .luajit.header import detect as luajit_detect
from .luajit.known import align as luajit_align
from .luajit.scramble import random_permutation as luajit_permutation
from .luajit.scramble import scramble as luajit_scramble
from .luajit.solve import solve as luajit_solve
from .luajit.verify import verify as luajit_verify


class NotBytecode(ValueError):
    pass


@dataclass
class Loaded:
    format: "Lua51 | LuaJIT"
    chunk: object
    header: object
    repairs: list[str] = field(default_factory=list)


class Lua51:
    name = "5.1"
    label = "Lua 5.1"
    names = lua51_opcodes.NAMES
    op = lua51_opcodes.OP
    unluac = True

    def load(self, data: bytes) -> Loaded:
        try:
            d = lua51_detect(data)
        except ChunkError as exc:
            raise NotBytecode(str(exc)) from exc
        return Loaded(self, d.chunk, d.header, d.repairs)

    def describe(self, loaded: Loaded) -> str:
        h = loaded.header
        return (f"Lua 5.1, size_t={h.sizeof_size_t}, "
                f"{'little' if h.little_endian else 'big'}-endian")

    def header_info(self, loaded: Loaded) -> dict:
        h = loaded.header
        return {"little_endian": h.little_endian, "sizeof_size_t": h.sizeof_size_t,
                "sizeof_number": h.sizeof_number}

    def solve(self, chunks, fixed=None):
        return lua51_solve(chunks, fixed=fixed)

    def align(self, game, stock):
        return lua51_align(game, stock)

    def verify(self, chunk):
        return lua51_verify(chunk)

    def dump(self, loaded: Loaded) -> bytes:
        h = loaded.header
        header = Lua51Header(little_endian=h.little_endian, sizeof_size_t=h.sizeof_size_t,
                             sizeof_number=h.sizeof_number, integral=h.integral)
        return lua51_dump(loaded.chunk, header)

    def strict_parse(self, data: bytes):
        from .lua51.chunk import parse
        try:
            return parse(data)
        except ChunkError as exc:
            raise NotBytecode(str(exc)) from exc

    def permutation(self, seed):
        return lua51_permutation(seed)

    def scramble(self, chunk, perm, **kw) -> bytes:
        return lua51_scramble(chunk, perm, **kw)


class LuaJIT:
    name = "luajit2.1"
    label = "LuaJIT 2.1"
    names = luajit_opcodes.NAMES
    op = luajit_opcodes.OP
    unluac = False

    def load(self, data: bytes) -> Loaded:
        try:
            d = luajit_detect(data)
        except BytecodeError as exc:
            raise NotBytecode(str(exc)) from exc
        return Loaded(self, d.dump, d.header, d.repairs)

    def describe(self, loaded: Loaded) -> str:
        h = loaded.header
        parts = ["LuaJIT 2.1", "big-endian" if h.big_endian else "little-endian",
                 "stripped" if h.stripped else "with debug info"]
        if h.fr2:
            parts.append("FR2")
        return ", ".join(parts)

    def header_info(self, loaded: Loaded) -> dict:
        return {"flags": loaded.header.flags}

    def solve(self, chunks, fixed=None):
        return luajit_solve(chunks, fixed=fixed)

    def align(self, game, stock):
        return luajit_align(game, stock)

    def verify(self, chunk):
        return luajit_verify(chunk)

    def dump(self, loaded: Loaded) -> bytes:
        h = loaded.header
        return luajit_dump(loaded.chunk, LuajitHeader(2, h.flags, h.chunkname))

    def strict_parse(self, data: bytes):
        from .luajit.bytecode import parse
        try:
            return parse(data)
        except BytecodeError as exc:
            raise NotBytecode(str(exc)) from exc

    def permutation(self, seed):
        return luajit_permutation(seed)

    def scramble(self, chunk, perm, **kw) -> bytes:
        return luajit_scramble(chunk, perm, **kw)


FORMATS = {f.name: f for f in (Lua51(), LuaJIT())}


def sniff(data: bytes) -> "Lua51 | LuaJIT":
    return FORMATS["luajit2.1" if data[:3] == LUAJIT_MAGIC else "5.1"]


def load(data: bytes, prefer: str | None = None) -> Loaded:
    first = FORMATS[prefer] if prefer else sniff(data)
    for fmt in (first, *(f for f in FORMATS.values() if f is not first)):
        try:
            return fmt.load(data)
        except NotBytecode:
            continue
    raise NotBytecode("not Lua 5.1 or LuaJIT 2.1 bytecode")
