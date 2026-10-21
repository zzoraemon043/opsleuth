import heapq
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from itertools import count

from .assign import INF, min_cost_assignment
from .model import Model

SOFT_PENALTY = 8.0
REPAIR_BUDGET = 400
UNMAPPED_COST = 1e9


class Contradiction(ValueError):
    pass


@dataclass(frozen=True)
class Dialect:
    names: tuple[str, ...]
    candidates: tuple[int, ...]
    last_ops: frozenset[int]
    valid: Callable
    requirements: Callable
    soft_penalty: Callable
    extract: Callable
    model: type[Model]


@dataclass
class OpResult:
    game: int
    op: int | None
    candidates: list[int]
    method: str
    margin: float | None = None
    count: int = 0

    def to_dict(self, names: tuple[str, ...]) -> dict:
        return {
            "game": self.game,
            "op": names[self.op] if self.op is not None else None,
            "candidates": [names[c] for c in self.candidates],
            "method": self.method,
            "margin": None if self.margin is None or self.margin == float("inf") else round(self.margin, 2),
            "count": self.count,
        }


@dataclass
class Solution:
    ops: dict[int, OpResult] = field(default_factory=dict)

    @property
    def mapping(self) -> dict[int, int]:
        return {g: r.op for g, r in self.ops.items() if r.op is not None}

    def ambiguous(self, threshold: float = 50.0) -> list[OpResult]:
        return [
            r for r in self.ops.values()
            if r.method == "score" and (r.margin is None or r.margin < threshold)
        ]


class _Problem:
    def __init__(self, chunks: Iterable, dialect: Dialect, fixed: dict[int, int] | None,
                 candidates: Iterable[int] | None = None):
        self.dialect = dialect
        self.candidates = tuple(dialect.candidates if candidates is None else candidates)
        self.occ: dict[int, list[tuple[object, int]]] = defaultdict(list)
        self.last_ops: set[int] = set()
        for chunk in chunks:
            for fn in chunk.functions():
                for pc, ins in enumerate(fn.code):
                    self.occ[ins.op].append((fn, pc))
                if fn.code:
                    self.last_ops.add(fn.code[-1].op)
        self.games = sorted(self.occ)
        self.dom: dict[int, set[int]] = {}
        self.req: dict[int, dict[int, dict[int, frozenset[int]]]] = {}
        self.fixed = fixed or {}

    def build_domains(self):
        for g in self.games:
            if g in self.fixed:
                candidates = [self.fixed[g]]
            elif g in self.last_ops:
                candidates = [s for s in self.candidates if s in self.dialect.last_ops]
            else:
                candidates = self.candidates
            dom = set()
            valid = self.dialect.valid
            for s in candidates:
                if all(valid(s, fn, pc) for fn, pc in self.occ[g]):
                    dom.add(s)
            self.dom[g] = dom
            self.req[g] = {s: self._requirements(g, s) for s in dom}
            self.req[g] = {s: r for s, r in self.req[g].items() if r is not None}
            self.dom[g] = set(self.req[g])

    def _requirements(self, g: int, s: int) -> dict[int, frozenset[int]] | None:
        need: dict[int, frozenset[int]] = {}
        for fn, pc in self.occ[g]:
            for target, allowed in self.dialect.requirements(s, fn, pc):
                if not 0 <= target < len(fn.code):
                    return None
                other = fn.code[target].op
                need[other] = need.get(other, allowed) & allowed
                if not need[other]:
                    return None
        claims: dict[int, int] = {}
        for other, allowed in need.items():
            if len(allowed) == 1:
                (t,) = allowed
                if claims.setdefault(t, other) != other:
                    return None
            if other == g and s not in allowed:
                return None
        return need

    def propagate(self):
        changed = True
        while changed:
            changed = False
            for g in self.games:
                for s in list(self.dom[g]):
                    if any(not (self.dom[o] & allowed) for o, allowed in self.req[g][s].items()):
                        self.dom[g].discard(s)
                        changed = True
                if not self.dom[g]:
                    raise Contradiction(f"no standard opcode fits game opcode {g}")
                if len(self.dom[g]) == 1:
                    (s,) = self.dom[g]
                    for o in self.games:
                        if o != g and s in self.dom[o]:
                            self.dom[o].discard(s)
                            changed = True
                    for o, allowed in self.req[g][s].items():
                        if not self.dom[o] <= allowed:
                            self.dom[o] &= allowed
                            changed = True

    def conflict(self, assignment: dict[int, int]) -> tuple[int, int] | None:
        for g, s in assignment.items():
            for o, allowed in self.req[g][s].items():
                if assignment.get(o) not in allowed:
                    return g, o
        return None


def _score_table(problem: _Problem, model: Model, known: dict[int, int]) -> dict[int, dict[int, float]]:
    table = {}
    for g in problem.games:
        if len(problem.dom[g]) == 1:
            continue
        feature_counts: Counter[tuple[str, str]] = Counter()
        soft: Counter[int] = Counter()
        dialect = problem.dialect
        for fn, pc in problem.occ[g]:
            for item in dialect.extract(fn, pc, known).items():
                feature_counts[item] += 1
            for s in problem.dom[g]:
                if dialect.soft_penalty(s, fn, pc):
                    soft[s] += 1
        n = len(problem.occ[g])
        scores = {}
        for s in problem.dom[g]:
            prior = model.log_prior[s] * n
            table_s = model.tables[s]
            total = prior
            for (family, value), times in feature_counts.items():
                known_values, unseen = table_s[family]
                total += times * known_values.get(value, unseen)
            scores[s] = total - SOFT_PENALTY * soft[s]
        table[g] = scores
    return table


def _assign(
    problem: _Problem, table: dict[int, dict[int, float]], banned: set[tuple[int, int]],
) -> dict[int, int]:
    fixed = {g: next(iter(problem.dom[g])) for g in problem.games if len(problem.dom[g]) == 1}
    free = [g for g in problem.games if g not in fixed]
    used = set(fixed.values())
    columns = [s for s in problem.candidates if s not in used]
    width = len(columns) + len(free)
    cost = []
    for g in free:
        row = []
        for s in columns:
            if s in problem.dom[g] and (g, s) not in banned:
                row.append(-table[g][s])
            else:
                row.append(INF)
        row.extend([UNMAPPED_COST] * len(free))
        cost.append(row)
    result = dict(fixed)
    if free:
        picks = min_cost_assignment(cost) if width else []
        for g, j in zip(free, picks, strict=True):
            if 0 <= j < len(columns) and cost[free.index(g)][j] != INF:
                result[g] = columns[j]
    return result


def solve(chunks: Iterable, dialect: Dialect, model: Model | None = None,
          fixed: dict[int, int] | None = None, candidates: Iterable[int] | None = None) -> Solution:
    model = model or dialect.model.default()
    problem = _Problem(chunks, dialect, fixed, candidates)
    problem.build_domains()
    problem.propagate()

    known = {g: next(iter(d)) for g, d in problem.dom.items() if len(d) == 1}
    banned: set[tuple[int, int]] = set()
    assignment = dict(known)
    table: dict[int, dict[int, float]] = {}
    for _ in range(3):
        table = _score_table(problem, model, assignment)
        assignment = _assign(problem, table, banned)
    assignment, banned = _repair(problem, table, assignment, banned)

    base = _total(table, assignment)
    solution = Solution()
    for g in problem.games:
        dom = sorted(problem.dom[g], key=lambda s: (-table.get(g, {}).get(s, 0.0), s))
        op = assignment.get(g)
        if g in problem.fixed:
            method = "given"
        elif len(dom) == 1:
            method = "constraint"
        else:
            method = "score"
        margin = None
        if method == "score" and op is not None:
            alternative = _assign(problem, table, banned | {(g, op)})
            if alternative.get(g) is None or problem.conflict(alternative) is not None:
                margin = None if alternative.get(g) is not None else float("inf")
            if margin is None:
                margin = base - _total(table, alternative)
        solution.ops[g] = OpResult(g, op, dom, method, margin, len(problem.occ[g]))
    return solution


def _repair(
    problem: _Problem, table: dict[int, dict[int, float]], assignment: dict[int, int],
    banned: set[tuple[int, int]],
) -> tuple[dict[int, int], set[tuple[int, int]]]:
    tie = count()
    frontier = [(-_total(table, assignment), next(tie), frozenset(banned), assignment)]
    seen = {frozenset(banned)}
    for _ in range(REPAIR_BUDGET):
        if not frontier:
            break
        _, _, ban, current = heapq.heappop(frontier)
        broken = problem.conflict(current)
        if broken is None:
            return current, set(ban)
        for g in broken:
            if g not in current or len(problem.dom[g]) == 1:
                continue
            child = ban | {(g, current[g])}
            if child in seen:
                continue
            seen.add(child)
            nxt = _assign(problem, table, set(child))
            heapq.heappush(frontier, (-_total(table, nxt), next(tie), child, nxt))
    return assignment, banned


def _total(table: dict[int, dict[int, float]], assignment: dict[int, int]) -> float:
    total = 0.0
    for g, scores in table.items():
        s = assignment.get(g)
        total += scores[s] if s is not None else -UNMAPPED_COST
    return total
