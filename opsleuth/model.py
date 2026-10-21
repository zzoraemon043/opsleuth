import json
import math
from collections import Counter, defaultdict
from importlib import resources


class Model:
    names: tuple[str, ...] = ()
    families: tuple[str, ...] = ()
    package: str = ""

    @staticmethod
    def extract(fn, pc: int, known: dict[int, int]) -> dict[str, str]:
        raise NotImplementedError

    def __init__(self, op_counts: dict[str, int], feature_counts: dict[str, dict[str, dict[str, int]]]):
        self.op_counts = op_counts
        self.feature_counts = feature_counts
        total = sum(op_counts.values())
        self.log_prior = [
            math.log((op_counts.get(name, 0) + 1) / (total + len(self.names))) for name in self.names
        ]
        self.tables: list[dict[str, tuple[dict[str, float], float]]] = []
        for name in self.names:
            per_family = {}
            for family in self.families:
                counts = feature_counts.get(name, {}).get(family, {})
                vocab = len(self._vocabulary(family)) + 1
                denom = sum(counts.values()) + vocab
                per_family[family] = (
                    {v: math.log((n + 1) / denom) for v, n in counts.items()},
                    math.log(1 / denom),
                )
            self.tables.append(per_family)

    def _vocabulary(self, family: str) -> set[str]:
        values = set()
        for per_op in self.feature_counts.values():
            values.update(per_op.get(family, {}))
        return values

    def log_likelihood(self, op: int, features: dict[str, str]) -> float:
        score = self.log_prior[op]
        table = self.tables[op]
        for family, value in features.items():
            known, unseen = table[family]
            score += known.get(value, unseen)
        return score

    def to_json(self) -> str:
        return json.dumps(
            {"op_counts": self.op_counts, "feature_counts": self.feature_counts},
            sort_keys=True, separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> "Model":
        data = json.loads(text)
        return cls(data["op_counts"], data["feature_counts"])

    @classmethod
    def default(cls) -> "Model":
        text = resources.files(cls.package).joinpath("model.json").read_text("utf-8")
        return cls.from_json(text)

    @classmethod
    def train(cls, chunks) -> "Model":
        op_counts: Counter[str] = Counter()
        feature_counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
        identity = {i: i for i in range(len(cls.names))}
        for chunk in chunks:
            for fn in chunk.functions():
                for pc, ins in enumerate(fn.code):
                    name = cls.names[ins.op]
                    op_counts[name] += 1
                    for family, value in cls.extract(fn, pc, identity).items():
                        feature_counts[name][family][value] += 1
        return cls(
            dict(op_counts),
            {op: {f: dict(c) for f, c in fams.items()} for op, fams in feature_counts.items()},
        )
