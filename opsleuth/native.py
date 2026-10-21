import re
import struct
from dataclasses import dataclass


@dataclass
class Segment:
    offset: int
    size: int
    vaddr: int


@dataclass
class Image:
    data: bytes
    kind: str
    pointer_size: int
    little_endian: bool
    segments: list[Segment]
    relocated: dict[int, int]

    def to_vaddr(self, offset: int) -> int | None:
        for seg in self.segments:
            if seg.offset <= offset < seg.offset + seg.size:
                return seg.vaddr + offset - seg.offset
        return None

    def to_offset(self, vaddr: int) -> int | None:
        for seg in self.segments:
            if seg.vaddr <= vaddr < seg.vaddr + seg.size:
                return seg.offset + vaddr - seg.vaddr
        return None


_RELATIVE = {(62, 8), (183, 1027), (40, 23), (3, 8), (8, 3), (20, 22), (21, 22)}


def _elf(data: bytes) -> Image:
    is64 = data[4] == 2
    little = data[5] == 1
    e = "<" if little else ">"
    if is64:
        (machine,) = struct.unpack_from(e + "H", data, 18)
        phoff, shoff = struct.unpack_from(e + "QQ", data, 32)
        phentsize, phnum, shentsize, shnum = struct.unpack_from(e + "HHHH", data, 54)
    else:
        (machine,) = struct.unpack_from(e + "H", data, 18)
        phoff, shoff = struct.unpack_from(e + "II", data, 28)
        phentsize, phnum, shentsize, shnum = struct.unpack_from(e + "HHHH", data, 42)
    segments = []
    for i in range(phnum):
        base = phoff + i * phentsize
        if is64:
            p_type, _, p_offset, p_vaddr, _, p_filesz = struct.unpack_from(e + "IIQQQQ", data, base)
        else:
            p_type, p_offset, p_vaddr, _, p_filesz = struct.unpack_from(e + "IIIII", data, base)
        if p_type == 1:
            segments.append(Segment(p_offset, p_filesz, p_vaddr))
    image = Image(data, "elf", 8 if is64 else 4, little, segments, {})
    for i in range(shnum):
        base = shoff + i * shentsize
        if base + shentsize > len(data):
            break
        layout = "IIQQQQIIQQ" if is64 else "IIIIIIIIII"
        _, sh_type, _, _, sh_offset, sh_size, _, _, _, sh_entsize = struct.unpack_from(e + layout, data, base)
        if sh_type not in (4, 9) or not sh_entsize:
            continue
        rela = sh_type == 4
        for off in range(sh_offset, sh_offset + sh_size, sh_entsize):
            if is64:
                r_offset, r_info = struct.unpack_from(e + "QQ", data, off)
                r_type = r_info & 0xFFFFFFFF
                addend = struct.unpack_from(e + "q", data, off + 16)[0] if rela else None
            else:
                r_offset, r_info = struct.unpack_from(e + "II", data, off)
                r_type = r_info & 0xFF
                addend = struct.unpack_from(e + "i", data, off + 8)[0] if rela else None
            if (machine, r_type) not in _RELATIVE:
                continue
            if addend is None:
                file_off = image.to_offset(r_offset)
                if file_off is None:
                    continue
                addend = struct.unpack_from(e + ("Q" if is64 else "I"), data, file_off)[0]
            image.relocated[r_offset] = addend
    return image


def _pe(data: bytes) -> Image:
    (pe_off,) = struct.unpack_from("<I", data, 0x3C)
    nsections, = struct.unpack_from("<H", data, pe_off + 6)
    opt_size, = struct.unpack_from("<H", data, pe_off + 20)
    opt = pe_off + 24
    magic, = struct.unpack_from("<H", data, opt)
    if magic == 0x20B:
        (image_base,) = struct.unpack_from("<Q", data, opt + 24)
        pointer_size = 8
    else:
        (image_base,) = struct.unpack_from("<I", data, opt + 28)
        pointer_size = 4
    segments = []
    table = opt + opt_size
    for i in range(nsections):
        base = table + i * 40
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", data, base + 8)
        segments.append(Segment(raw_ptr, min(raw_size, vsize or raw_size), image_base + vaddr))
    return Image(data, "pe", pointer_size, True, segments, {})


def load(data: bytes) -> Image:
    if data[:4] == b"\x7fELF":
        return _elf(data)
    if data[:2] == b"MZ":
        return _pe(data)
    return Image(data, "raw", 8, True, [Segment(0, len(data), 0)], {})


_NAME = re.compile(rb"(?<=\0)[A-Z][A-Z0-9_]{1,15}(?=\0)")


@dataclass
class OpnameTable:
    offset: int
    names: list[str]


def find_opname_tables(data: bytes, known_names: set[str], min_hits: int = 20) -> list[OpnameTable]:
    image = load(data)
    strings: dict[int, str] = {}
    for m in _NAME.finditer(data):
        vaddr = image.to_vaddr(m.start())
        if vaddr is None:
            continue
        text = m.group().decode()
        for k in range(len(text) - 1):
            strings[vaddr + k] = text[k:]
    targets = {v for v, s in strings.items() if s in known_names}
    if len(targets) < min_hits:
        return []
    size = image.pointer_size
    fmt = ("<" if image.little_endian else ">") + ("Q" if size == 8 else "I")
    slots: dict[int, int] = {}
    for seg in image.segments:
        start = seg.offset + (-seg.vaddr % size)
        end = min(seg.offset + seg.size, len(data)) - size
        for off in range(start, end + 1, size):
            (value,) = struct.unpack_from(fmt, data, off)
            if value in strings:
                slots[seg.vaddr + off - seg.offset] = value
    for where, value in image.relocated.items():
        if value in strings:
            slots[where] = value
    tables = []
    seen: set[int] = set()
    for where in sorted(slots):
        if where in seen or where - size in slots:
            continue
        run = []
        cursor = where
        while cursor in slots:
            seen.add(cursor)
            run.append(strings[slots[cursor]])
            cursor += size
        hits = sum(1 for name in run if name in known_names)
        if hits >= min_hits and len(set(run)) == len(run):
            offset = image.to_offset(where)
            tables.append(OpnameTable(offset if offset is not None else where, run))
    return tables
