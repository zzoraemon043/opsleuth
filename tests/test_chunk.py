import random

import pytest

from opsleuth.lua51 import rules
from opsleuth.lua51.chunk import ChunkError, Header, dump, parse
from opsleuth.lua51.header import detect
from opsleuth.lua51.opcodes import NAMES, RETURN
from opsleuth.lua51.scramble import damaged_header, strip
from opsleuth.lua51.verify import verify


def test_round_trip(fixture_files):
    for path in fixture_files:
        data = path.read_bytes()
        assert dump(parse(data)) == data


def test_fixtures_use_every_opcode(chunks):
    used = {ins.op for c in chunks for fn in c.functions() for ins in fn.code}
    assert used == set(range(len(NAMES)))


def test_rules_accept_stock_bytecode(chunks):
    for chunk in chunks:
        for fn in chunk.functions():
            assert fn.code[-1].op == RETURN
            for pc, ins in enumerate(fn.code):
                assert rules.valid(ins.op, fn, pc), (NAMES[ins.op], pc)
                for target, allowed in rules.requirements(ins.op, fn, pc):
                    assert fn.code[target].op in allowed
        assert verify(chunk).ok


def test_truncated_chunk_is_rejected(fixture_files):
    data = fixture_files[0].read_bytes()
    with pytest.raises(ChunkError):
        parse(data[:-3])


def test_stripped_chunk_round_trips(chunks):
    for chunk in chunks:
        strip(chunk)
        data = dump(chunk)
        assert dump(parse(data)) == data


@pytest.mark.parametrize("seed", range(8))
def test_damaged_header_is_repaired(fixture_files, seed):
    data = fixture_files[seed % len(fixture_files)].read_bytes()
    broken = damaged_header(parse(data).header, random.Random(seed)) + data[12:]
    found = detect(broken)
    assert found.repairs
    assert dump(found.chunk, Header(sizeof_size_t=found.header.sizeof_size_t)) == data


def test_missing_header_is_detected(fixture_files):
    data = fixture_files[0].read_bytes()
    found = detect(data[12:])
    assert found.offset == 0
    assert dump(found.chunk, Header(sizeof_size_t=found.header.sizeof_size_t)) == data


def test_big_endian_round_trip(fixture_files):
    chunk = parse(fixture_files[0].read_bytes())
    big = Header(little_endian=False, sizeof_size_t=4)
    data = dump(chunk, big)
    found = detect(data)
    assert not found.header.little_endian
    assert dump(found.chunk) == data
