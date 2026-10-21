from ..lua51.verify import Report
from . import rules
from .bytecode import Dump
from .opcodes import NAMES, NOT_DUMPED, NUM_OPCODES
from .solve import DIALECT


def verify(d: Dump, limit: int = 20) -> Report:
    report = Report()
    for index, fn in enumerate(d.protos):
        if not fn.code or fn.code[-1].op not in DIALECT.last_ops:
            report.problems.append(f"function {index}: does not end with a return")
        for pc, ins in enumerate(fn.code):
            report.instructions += 1
            if ins.op >= NUM_OPCODES or ins.op in NOT_DUMPED:
                report.problems.append(f"function {index} pc {pc}: opcode {ins.op} not valid in a dump")
                continue
            if not rules.valid(ins.op, fn, pc):
                report.problems.append(f"function {index} pc {pc}: invalid operands for {NAMES[ins.op]}")
                continue
            for target, allowed in rules.requirements(ins.op, fn, pc):
                if not 0 <= target < len(fn.code) or fn.code[target].op not in allowed:
                    expected = "/".join(NAMES[a] for a in sorted(allowed))
                    report.problems.append(
                        f"function {index} pc {pc}: {NAMES[ins.op]} expects {expected} at pc {target}"
                    )
            if len(report.problems) >= limit:
                return report
    return report
