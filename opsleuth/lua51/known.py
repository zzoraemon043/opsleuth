from collections import Counter, defaultdict

from .chunk import Chunk, Function


def _signature(fn: Function) -> tuple:
    constants = tuple((k.type, k.value) for k in fn.constants)
    operands = tuple(ins.raw >> 6 for ins in fn.code)
    return len(fn.code), constants, operands, len(fn.protos), fn.nups, fn.num_params


def align(game_chunks: list[Chunk], stock_chunks: list[Chunk]) -> tuple[dict[int, int], int]:
    index: dict[tuple, Function | None] = {}
    for chunk in stock_chunks:
        for fn in chunk.functions():
            key = _signature(fn)
            if key in index and index[key] is not None and index[key].code != fn.code:
                index[key] = None
            else:
                index.setdefault(key, fn)
    votes: dict[int, Counter] = defaultdict(Counter)
    matched = 0
    for chunk in game_chunks:
        for fn in chunk.functions():
            stock = index.get(_signature(fn))
            if stock is not None:
                matched += 1
                for g, s in zip(fn.code, stock.code, strict=True):
                    votes[g.op][s.op] += 1
    mapping = {}
    for g, counter in votes.items():
        (s, n), *rest = counter.most_common()
        if not rest or n >= 10 * rest[0][1]:
            mapping[g] = s
    taken = Counter(mapping.values())
    return {g: s for g, s in mapping.items() if taken[s] == 1}, matched
