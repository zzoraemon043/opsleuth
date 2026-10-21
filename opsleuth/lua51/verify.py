from dataclasses import dataclass, field

from . import rules
from .chunk import Chunk
from .opcodes import NAMES, NUM_OPCODES, RETURN


@dataclass
class Report:
    instructions: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def verify(chunk: Chunk, limit: int = 20) -> Report:
    report = Report()
    for index, fn in enumerate(chunk.functions()):
        if not fn.code or fn.code[-1].op != RETURN:
            report.problems.append(f"function {index}: does not end with RETURN")
        for pc, ins in enumerate(fn.code):
            report.instructions += 1
            if ins.op >= NUM_OPCODES:
                report.problems.append(f"function {index} pc {pc}: opcode {ins.op} out of range")
                continue
            if not rules.valid(ins.op, fn, pc):
                report.problems.append(f"function {index} pc {pc}: invalid operands for {NAMES[ins.op]}")
                continue
            for target, allowed in rules.requirements(ins.op, fn, pc):
                if fn.code[target].op not in allowed:
                    expected = "/".join(NAMES[a] for a in sorted(allowed))
                    report.problems.append(
                        f"function {index} pc {pc}: {NAMES[ins.op]} expects {expected} at pc {target}"
                    )
            if len(report.problems) >= limit:
                return report
    return report
