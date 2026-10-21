import struct
from dataclasses import dataclass

from .opcodes import Instruction

MAGIC = b"\x1bLJ"
F_BE, F_STRIP, F_FFI, F_FR2, F_BITOP = 0x01, 0x02, 0x04, 0x08, 0x10
PROTO_VARARG, PROTO_FFI, PROTO_BITOP = 0x02, 0x04, 0x80

KGC_CHILD, KGC_TAB, KGC_I64, KGC_U64, KGC_COMPLEX, KGC_STR = range(6)
KTAB_NIL, KTAB_FALSE, KTAB_TRUE, KTAB_INT, KTAB_NUM, KTAB_STR = range(6)


class BytecodeError(ValueError):
    pass


@dataclass
class Header:
    version: int = 2
    flags: int = F_STRIP
    chunkname: bytes | None = None

    @property
    def big_endian(self) -> bool:
        return bool(self.flags & F_BE)

    @property
    def stripped(self) -> bool:
        return bool(self.flags & F_STRIP)

    @property
    def fr2(self) -> bool:
        return bool(self.flags & F_FR2)

    def encode(self) -> bytes:
        out = bytearray(MAGIC)
        out.append(self.version)
        out += _uleb(self.flags)
        if not self.stripped:
            name = self.chunkname or b""
            out += _uleb(len(name)) + name
        return bytes(out)


@dataclass
class Proto:
    flags: int
    numparams: int
    framesize: int
    uv: list[int]
    kgc: list[tuple]
    kn: list[float | int]
    code: list[Instruction]
    debug: bytes = b""
    prefix: bytes = b""
    suffix: bytes = b""

    @property
    def is_vararg(self) -> bool:
        return bool(self.flags & PROTO_VARARG)

    @property
    def uses_ffi(self) -> bool:
        return bool(self.flags & PROTO_FFI)

    @property
    def uses_bitops(self) -> bool:
        return bool(self.flags & PROTO_BITOP)

    def kgc_at(self, index: int) -> tuple | None:
        if 0 <= index < len(self.kgc):
            return self.kgc[len(self.kgc) - 1 - index]
        return None


@dataclass
class Dump:
    header: Header
    protos: list[Proto]

    @property
    def main(self) -> Proto:
        return self.protos[-1]

    def functions(self) -> list[Proto]:
        return self.protos


def _uleb(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


class _Reader:
    def __init__(self, data: bytes, pos: int = 0, end: int | None = None):
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def need(self, n: int) -> None:
        if self.pos + n > self.end:
            raise BytecodeError("unexpected end of data")

    def byte(self) -> int:
        self.need(1)
        self.pos += 1
        return self.data[self.pos - 1]

    def bytes(self, n: int) -> bytes:
        self.need(n)
        self.pos += n
        return self.data[self.pos - n:self.pos]

    def uleb(self) -> int:
        value = shift = 0
        while True:
            b = self.byte()
            value |= (b & 0x7F) << shift
            if b < 0x80:
                return value
            shift += 7
            if shift > 35:
                raise BytecodeError("ULEB128 too long")

    def uleb33(self) -> tuple[int, bool]:
        first = self.byte()
        value = first >> 1
        if value >= 0x40:
            value &= 0x3F
            shift = 6
            while True:
                b = self.byte()
                value |= (b & 0x7F) << shift
                shift += 7
                if b < 0x80:
                    break
                if shift > 40:
                    raise BytecodeError("ULEB128 too long")
        return value, bool(first & 1)


def _ktabk(r: _Reader) -> tuple:
    tp = r.uleb()
    if tp >= KTAB_STR:
        return ("str", r.bytes(tp - KTAB_STR))
    if tp == KTAB_INT:
        return ("int", r.uleb())
    if tp == KTAB_NUM:
        lo, hi = r.uleb(), r.uleb()
        return ("num", lo | hi << 32)
    return ("pri", tp)


def _kgc(r: _Reader) -> tuple:
    tp = r.uleb()
    if tp >= KGC_STR:
        return ("str", r.bytes(tp - KGC_STR))
    if tp == KGC_CHILD:
        return ("child",)
    if tp == KGC_TAB:
        narray, nhash = r.uleb(), r.uleb()
        array = [_ktabk(r) for _ in range(narray)]
        pairs = [(_ktabk(r), _ktabk(r)) for _ in range(nhash)]
        return ("tab", array, pairs)
    if tp in (KGC_I64, KGC_U64):
        lo, hi = r.uleb(), r.uleb()
        return ("i64" if tp == KGC_I64 else "u64", lo | hi << 32)
    if tp == KGC_COMPLEX:
        return ("complex", tuple(r.uleb() for _ in range(4)))
    raise BytecodeError(f"bad constant type {tp}")


def _knum(r: _Reader) -> float | int:
    lo, is_num = r.uleb33()
    if not is_num:
        return lo - (1 << 32) if lo & 0x80000000 else lo
    hi = r.uleb()
    if hi >> 32 or lo >> 32:
        raise BytecodeError("bad number constant")
    return struct.unpack("<d", struct.pack("<Q", lo | hi << 32))[0]


def _proto(data: bytes, start: int, end: int, header: Header, stack: list[Proto]) -> Proto:
    r = _Reader(data, start, end)
    flags, numparams, framesize, sizeuv = r.byte(), r.byte(), r.byte(), r.byte()
    sizekgc, sizekn, sizebc = r.uleb(), r.uleb(), r.uleb()
    sizedbg = 0
    if not header.stripped:
        sizedbg = r.uleb()
        if sizedbg:
            r.uleb()
            r.uleb()
    if sizebc > end - r.pos or sizekgc > end - r.pos or sizekn > end - r.pos:
        raise BytecodeError("bad prototype sizes")
    prefix = data[start:r.pos]
    order = ">" if header.big_endian else "<"
    code = [Instruction(w) for w in struct.unpack(f"{order}{sizebc}I", r.bytes(4 * sizebc))]
    code_end = r.pos
    uv = list(struct.unpack(f"{order}{sizeuv}H", r.bytes(2 * sizeuv)))
    kgc = [_kgc(r) for _ in range(sizekgc)]
    kn = [_knum(r) for _ in range(sizekn)]
    debug = r.bytes(sizedbg)
    if r.pos != end:
        raise BytecodeError("prototype size mismatch")
    for i, k in enumerate(kgc):
        if k[0] == "child":
            if not stack:
                raise BytecodeError("missing child prototype")
            kgc[i] = ("child", stack.pop())
    return Proto(flags, numparams, framesize, uv, kgc, kn, code, debug,
                 prefix, data[code_end:end])


def parse_header(data: bytes) -> tuple[Header, int]:
    if data[:3] != MAGIC:
        raise BytecodeError("not LuaJIT bytecode")
    r = _Reader(data, 3)
    version = r.byte()
    flags = r.uleb()
    name = None
    if not flags & F_STRIP:
        name = r.bytes(r.uleb())
    return Header(version, flags, name), r.pos


def parse_body(data: bytes, header: Header, pos: int) -> Dump:
    r = _Reader(data, pos)
    protos: list[Proto] = []
    stack: list[Proto] = []
    while True:
        if r.pos == len(data):
            break
        length = r.uleb()
        if length == 0:
            break
        r.need(length)
        proto = _proto(data, r.pos, r.pos + length, header, stack)
        r.pos += length
        protos.append(proto)
        stack.append(proto)
    if r.pos != len(data):
        raise BytecodeError("trailing data")
    if len(stack) != 1:
        raise BytecodeError("dangling prototypes")
    return Dump(header, protos)


def parse(data: bytes) -> Dump:
    header, pos = parse_header(data)
    return parse_body(data, header, pos)


def dump(d: Dump, header: Header | None = None) -> bytes:
    header = header or d.header
    out = bytearray(header.encode())
    order = ">" if header.big_endian else "<"
    for proto in d.protos:
        code = struct.pack(f"{order}{len(proto.code)}I", *(ins.raw for ins in proto.code))
        body = proto.prefix + code + proto.suffix
        out += _uleb(len(body)) + body
    out.append(0)
    return bytes(out)
