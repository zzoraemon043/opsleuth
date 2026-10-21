import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .lua51 import opcodes
from .lua51.chunk import ChunkError, Header, dump, parse
from .lua51.header import detect
from .lua51.known import align
from .lua51.scramble import random_permutation, scramble
from .lua51.solve import Contradiction, solve
from .lua51.verify import verify
from .native import find_opname_tables

MAP_FORMAT = "opsleuth-map"


def _files(paths: list[Path]) -> list[tuple[Path, Path]]:
    out = []
    for root in paths:
        if root.is_dir():
            out.extend((f, f.relative_to(root)) for f in sorted(root.rglob("*")) if f.is_file())
        else:
            out.append((root, Path(root.name)))
    return out


def _load(paths: list[Path], quiet: bool = False):
    loaded = []
    skipped = 0
    for path, rel in _files(paths):
        try:
            loaded.append((path, rel, detect(path.read_bytes())))
        except ChunkError:
            skipped += 1
    if skipped and not quiet:
        print(f"skipped {skipped} file(s) that are not Lua 5.1 chunks", file=sys.stderr)
    return loaded


def cmd_detect(args) -> int:
    loaded = _load(args.paths)
    for path, _, d in loaded:
        h = d.header
        ops = sorted({ins.op for fn in d.chunk.functions() for ins in fn.code})
        status = "standard header" if not d.repairs else "; ".join(d.repairs)
        print(f"{path}: Lua 5.1, size_t={h.sizeof_size_t}, "
              f"{'little' if h.little_endian else 'big'}-endian, {len(ops)} opcodes used, {status}")
        if args.verbose:
            report = verify(d.chunk)
            print("  stock opcode order:", "looks standard" if report.ok else "does not match")
    return 0 if loaded else 1


def _native_candidates(lib: Path) -> list[dict[int, int]]:
    tables = find_opname_tables(lib.read_bytes(), set(opcodes.NAMES))
    out = []
    for table in tables:
        fixed = {i: opcodes.OP[name] for i, name in enumerate(table.names) if name in opcodes.OP}
        out.append(fixed)
        print(f"opname table at file offset 0x{table.offset:x}: {len(table.names)} entries",
              file=sys.stderr)
    return out


def cmd_solve(args) -> int:
    loaded = _load(args.paths)
    if not loaded:
        print("no Lua 5.1 chunks found", file=sys.stderr)
        return 1
    chunks = [d.chunk for _, _, d in loaded]
    attempts: list[tuple[dict[int, int] | None, str]] = []
    if args.known:
        stock = [d.chunk for _, _, d in _load([args.known], quiet=True)]
        known, matched = align(chunks, stock)
        print(f"known bytecode: {matched} function(s) matched, {len(known)} opcode(s) fixed",
              file=sys.stderr)
        if known:
            attempts.append((known, "known"))
    if args.lib:
        attempts.extend((fixed, "native") for fixed in _native_candidates(args.lib))
        if not attempts:
            print("no opname table found in the library; solving from bytecode only",
                  file=sys.stderr)
    attempts.append((None, "bytecode"))
    solution = None
    for fixed, source in attempts:
        try:
            solution = solve(chunks, fixed=fixed)
        except Contradiction as exc:
            print(f"{source} candidate rejected: {exc}", file=sys.stderr)
            continue
        for result in solution.ops.values():
            if result.method == "given":
                result.method = source
        break
    if solution is None:
        print("no consistent opcode mapping exists", file=sys.stderr)
        return 1
    header = loaded[0][2].header
    data = {
        "format": MAP_FORMAT,
        "version": 1,
        "lua": "5.1",
        "files": len(loaded),
        "header": {"little_endian": header.little_endian, "sizeof_size_t": header.sizeof_size_t,
                   "sizeof_number": header.sizeof_number},
        "ops": [r.to_dict() for r in sorted(solution.ops.values(), key=lambda r: r.game)],
        "ambiguous": [r.game for r in solution.ambiguous()],
    }
    text = json.dumps(data, indent=2)
    if args.output:
        args.output.write_text(text + "\n", "utf-8")
    else:
        print(text)
    _summary(solution, len(loaded))
    return 0


def _summary(solution, files: int) -> None:
    methods: dict[str, int] = {}
    for r in solution.ops.values():
        methods[r.method] = methods.get(r.method, 0) + 1
    parts = ", ".join(f"{n} by {m}" for m, n in sorted(methods.items()))
    print(f"{len(solution.ops)} opcodes from {files} file(s): {parts}", file=sys.stderr)
    for r in solution.ambiguous():
        chosen = opcodes.NAMES[r.op] if r.op is not None else "?"
        others = ", ".join(opcodes.NAMES[c] for c in r.candidates if c != r.op)
        print(f"  low confidence: game {r.game} -> {chosen} (also possible: {others})",
              file=sys.stderr)


def _read_map(path: Path) -> dict[int, int]:
    data = json.loads(path.read_text("utf-8"))
    if data.get("format") != MAP_FORMAT:
        raise SystemExit(f"{path} is not an opsleuth map")
    return {int(op["game"]): opcodes.OP[op["op"]] for op in data["ops"] if op["op"]}


def cmd_apply(args) -> int:
    mapping = _read_map(args.map)
    loaded = _load(args.paths)
    failures = 0
    for _, rel, d in loaded:
        unknown = 0
        for fn in d.chunk.functions():
            code = []
            for ins in fn.code:
                if ins.op not in mapping:
                    unknown += 1
                code.append(ins.with_op(mapping.get(ins.op, ins.op)))
            fn.code = code
        header = Header(little_endian=d.header.little_endian, sizeof_size_t=d.header.sizeof_size_t,
                        sizeof_number=d.header.sizeof_number, integral=d.header.integral)
        target = args.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(dump(d.chunk, header))
        if unknown:
            failures += 1
            print(f"{rel}: {unknown} instruction(s) with unmapped opcodes", file=sys.stderr)
    print(f"wrote {len(loaded)} file(s) to {args.output}", file=sys.stderr)
    return 1 if failures else 0


def cmd_verify(args) -> int:
    bad = 0
    total = 0
    unluac = Path(args.unluac) if args.unluac else None
    java = shutil.which("java") if unluac else None
    if unluac and not java:
        print("java not found; skipping decompiler check", file=sys.stderr)
    for path, rel in _files(args.paths):
        total += 1
        try:
            chunk = parse(path.read_bytes())
        except ChunkError as exc:
            print(f"{rel}: cannot parse with a standard header ({exc})")
            bad += 1
            continue
        report = verify(chunk)
        problem = None if report.ok else report.problems[0]
        if problem is None and java:
            run = subprocess.run([java, "-jar", str(unluac), str(path)], capture_output=True)
            if run.returncode != 0:
                problem = "decompiler failed: " + run.stderr.decode(errors="replace").strip()[:200]
        if problem:
            bad += 1
            print(f"{rel}: {problem}")
    print(f"{total - bad}/{total} file(s) passed", file=sys.stderr)
    return 1 if bad else 0


def cmd_scramble(args) -> int:
    perm = random_permutation(args.seed)
    for path, rel in _files(args.paths):
        try:
            chunk = parse(path.read_bytes())
        except ChunkError:
            continue
        target = args.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(scramble(chunk, perm, strip_debug=args.strip,
                                    damage_header=args.damage_header, seed=args.seed))
    if args.answer:
        answer = {"format": MAP_FORMAT, "version": 1, "lua": "5.1",
                  "ops": [{"game": g, "op": opcodes.NAMES[s]} for s, g in sorted(perm.items())]}
        args.answer.write_text(json.dumps(answer, indent=2) + "\n", "utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opsleuth", description=(
        "Recover the opcode order of Lua bytecode whose opcodes were renumbered."))
    parser.add_argument("--version", action="version", version=f"opsleuth {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("detect", help="identify chunks and header changes")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("solve", help="infer the opcode mapping")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--lib", type=Path, help="native library that embeds the Lua VM")
    p.add_argument("--known", type=Path,
                   help="stock luac output for some of the same scripts")
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("apply", help="rewrite chunks to stock opcodes and header")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--map", type=Path, required=True)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("verify", help="check that chunks are consistent stock bytecode")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--unluac", help="path to unluac.jar for a decompiler check")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("scramble", help="make test data by renumbering opcodes")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--strip", action="store_true", help="drop debug information")
    p.add_argument("--damage-header", action="store_true")
    p.add_argument("--answer", type=Path, help="write the true mapping here")
    p.set_defaults(func=cmd_scramble)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
