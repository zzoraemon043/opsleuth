import struct
from dataclasses import dataclass, field

from .opcodes import Instruction

SIGNATURE = b"\x1bLua"
VERSION = 0x51


class ChunkError(ValueError):
    pass


@dataclass
class Header:
    signature: bytes = SIGNATURE
    version: int = VERSION
    format: int = 0
    little_endian: bool = True
    sizeof_int: int = 4
    sizeof_size_t: int = 4
    sizeof_instruction: int = 4
    sizeof_number: int = 8
    integral: bool = False

    def encode(self) -> bytes:
        return self.signature + bytes((
            self.version, self.format, int(self.little_endian),
            self.sizeof_int, self.sizeof_size_t, self.sizeof_instruction,
            self.sizeof_number, int(self.integral),
        ))

    def is_standard(self) -> bool:
        return (
            self.signature == SIGNATURE and self.version == VERSION
            and self.format == 0 and self.sizeof_int == 4
            and self.sizeof_size_t in (4, 8) and self.sizeof_instruction == 4
            and self.sizeof_number in (4, 8) and not self.integral
        )


NIL, BOOLEAN, NUMBER, STRING = 0, 1, 3, 4


@dataclass
class Constant:
    type: int
    value: object = None


@dataclass
class LocVar:
    name: bytes | None
    startpc: int
    endpc: int


@dataclass
class Function:
    source: bytes | None
    line_defined: int
    last_line_defined: int
    nups: int
    num_params: int
    is_vararg: int
    max_stack: int
    code: list[Instruction] = field(default_factory=list)
    constants: list[Constant] = field(default_factory=list)
    protos: list["Function"] = field(default_factory=list)
    line_info: list[int] = field(default_factory=list)
    loc_vars: list[LocVar] = field(default_factory=list)
    upvalue_names: list[bytes | None] = field(default_factory=list)

    def walk(self):
        yield self
        for proto in self.protos:
            yield from proto.walk()


@dataclass
class Chunk:
    header: Header
    main: Function

    def functions(self):
        return list(self.main.walk())


class _Reader:
    def __init__(self, data: bytes, header: Header):
        sizes = (header.sizeof_int, header.sizeof_size_t, header.sizeof_number)
        if any(n not in (4, 8) for n in sizes) or header.sizeof_instruction != 4:
            raise ChunkError("unsupported type sizes in header")
        self.data = data
        self.pos = 0
        self.header = header
        e = "<" if header.little_endian else ">"
        self.int_fmt = e + {4: "i", 8: "q"}[header.sizeof_int]
        self.size_fmt = e + {4: "I", 8: "Q"}[header.sizeof_size_t]
        self.ins_fmt = e + "I"
        self.num_fmt = e + {4: "f", 8: "d"}[header.sizeof_number]
        if header.integral:
            self.num_fmt = e + {4: "i", 8: "q"}[header.sizeof_number]

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise ChunkError(f"truncated at offset {self.pos}")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def unpack(self, fmt: str):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def byte(self) -> int:
        return self.take(1)[0]

    def int(self) -> int:
        return self.unpack(self.int_fmt)

    def count(self) -> int:
        n = self.int()
        if n < 0 or n > len(self.data):
            raise ChunkError(f"bad count {n} at offset {self.pos}")
        return n

    def string(self) -> bytes | None:
        n = self.unpack(self.size_fmt)
        if n == 0:
            return None
        if n > len(self.data):
            raise ChunkError(f"bad string size {n} at offset {self.pos}")
        s = self.take(n)
        if s[-1] != 0:
            raise ChunkError(f"string without terminator at offset {self.pos}")
        return s[:-1]

    def function(self, depth: int = 0) -> Function:
        if depth > 200:
            raise ChunkError("functions nested too deeply")
        fn = Function(
            source=self.string(), line_defined=self.int(),
            last_line_defined=self.int(), nups=self.byte(),
            num_params=self.byte(), is_vararg=self.byte(),
            max_stack=self.byte(),
        )
        n = self.count()
        raw = self.take(4 * n)
        fn.code = [Instruction(v) for v in struct.unpack(f"{self.ins_fmt[0]}{n}I", raw)]
        for _ in range(self.count()):
            t = self.byte()
            if t == NIL:
                fn.constants.append(Constant(NIL))
            elif t == BOOLEAN:
                fn.constants.append(Constant(BOOLEAN, self.byte() != 0))
            elif t == NUMBER:
                fn.constants.append(Constant(NUMBER, self.unpack(self.num_fmt)))
            elif t == STRING:
                fn.constants.append(Constant(STRING, self.string()))
            else:
                raise ChunkError(f"bad constant type {t} at offset {self.pos - 1}")
        fn.protos = [self.function(depth + 1) for _ in range(self.count())]
        fn.line_info = [self.int() for _ in range(self.count())]
        for _ in range(self.count()):
            fn.loc_vars.append(LocVar(self.string(), self.int(), self.int()))
        fn.upvalue_names = [self.string() for _ in range(self.count())]
        return fn


def parse(data: bytes, header: Header | None = None, offset: int = 12) -> Chunk:
    if header is None:
        header = read_header(data)
    reader = _Reader(data, header)
    reader.pos = offset
    main = reader.function()
    if reader.pos != len(data):
        raise ChunkError(f"{len(data) - reader.pos} trailing bytes")
    return Chunk(header, main)


def read_header(data: bytes) -> Header:
    if len(data) < 12:
        raise ChunkError("file shorter than a Lua 5.1 header")
    return Header(
        signature=data[0:4], version=data[4], format=data[5],
        little_endian=data[6] != 0, sizeof_int=data[7],
        sizeof_size_t=data[8], sizeof_instruction=data[9],
        sizeof_number=data[10], integral=data[11] != 0,
    )


class _Writer:
    def __init__(self, header: Header):
        self.out = bytearray()
        e = "<" if header.little_endian else ">"
        self.int_fmt = e + {4: "i", 8: "q"}[header.sizeof_int]
        self.size_fmt = e + {4: "I", 8: "Q"}[header.sizeof_size_t]
        self.ins_fmt = e + "I"
        self.num_fmt = e + {4: "f", 8: "d"}[header.sizeof_number]
        if header.integral:
            self.num_fmt = e + {4: "i", 8: "q"}[header.sizeof_number]

    def pack(self, fmt: str, value):
        self.out += struct.pack(fmt, value)

    def string(self, s: bytes | None):
        if s is None:
            self.pack(self.size_fmt, 0)
        else:
            self.pack(self.size_fmt, len(s) + 1)
            self.out += s + b"\0"

    def function(self, fn: Function):
        self.string(fn.source)
        self.pack(self.int_fmt, fn.line_defined)
        self.pack(self.int_fmt, fn.last_line_defined)
        self.out += bytes((fn.nups, fn.num_params, fn.is_vararg, fn.max_stack))
        self.pack(self.int_fmt, len(fn.code))
        for ins in fn.code:
            self.pack(self.ins_fmt, ins.raw)
        self.pack(self.int_fmt, len(fn.constants))
        for k in fn.constants:
            self.out.append(k.type)
            if k.type == BOOLEAN:
                self.out.append(int(bool(k.value)))
            elif k.type == NUMBER:
                self.pack(self.num_fmt, k.value)
            elif k.type == STRING:
                self.string(k.value)
        self.pack(self.int_fmt, len(fn.protos))
        for proto in fn.protos:
            self.function(proto)
        self.pack(self.int_fmt, len(fn.line_info))
        for line in fn.line_info:
            self.pack(self.int_fmt, line)
        self.pack(self.int_fmt, len(fn.loc_vars))
        for var in fn.loc_vars:
            self.string(var.name)
            self.pack(self.int_fmt, var.startpc)
            self.pack(self.int_fmt, var.endpc)
        self.pack(self.int_fmt, len(fn.upvalue_names))
        for name in fn.upvalue_names:
            self.string(name)


def dump(chunk: Chunk, header: Header | None = None) -> bytes:
    header = header or chunk.header
    writer = _Writer(header)
    writer.out += header.encode()
    writer.function(chunk.main)
    return bytes(writer.out)
