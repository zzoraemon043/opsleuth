import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .formats import FORMATS, Loaded, NotBytecode, load, sniff
from .native import find_opname_tables
from .solver import Contradiction

MAP_FORMAT = "opsleuth-map"


def _files(paths: list[Path]) -> list[tuple[Path, Path]]:
    out = []
    for root in paths:
        if root.is_dir():
            out.extend((f, f.relative_to(root)) for f in sorted(root.rglob("*")) if f.is_file())
        else:
            out.append((root, Path(root.name)))
    return out


def _load(paths: list[Path], quiet: bool = False,
          prefer: str | None = None) -> list[tuple[Path, Path, Loaded]]:
    loaded = []
    skipped = 0
    for path, rel in _files(paths):
        try:
            loaded.append((path, rel, load(path.read_bytes(), prefer)))
        except NotBytecode:
            skipped += 1
    if skipped and not quiet:
        print(f"skipped {skipped} file(s) that are not Lua 5.1 or LuaJIT 2.1 bytecode",
              file=sys.stderr)
    return loaded


def _one_format(loaded: list[tuple[Path, Path, Loaded]]) -> list[tuple[Path, Path, Loaded]]:
    counts: dict[str, int] = {}
    for _, _, item in loaded:
        counts[item.format.name] = counts.get(item.format.name, 0) + 1
    if len(counts) > 1:
        main_format = max(counts, key=counts.get)
        dropped = len(loaded) - counts[main_format]
        print(f"mixed bytecode formats; using {counts[main_format]} {main_format} file(s), "
              f"ignoring {dropped}", file=sys.stderr)
        loaded = [x for x in loaded if x[2].format.name == main_format]
    return loaded


def cmd_detect(args) -> int:
    loaded = _load(args.paths)
    for path, _, item in loaded:
        ops = sorted({ins.op for fn in item.chunk.functions() for ins in fn.code})
        status = "standard header" if not item.repairs else "; ".join(item.repairs)
        print(f"{path}: {item.format.describe(item)}, {len(ops)} opcodes used, {status}")
        if args.verbose:
            report = item.format.verify(item.chunk)
            print("  stock opcode order:", "looks standard" if report.ok else "does not match")
    return 0 if loaded else 1


def _native_candidates(fmt, lib: Path) -> list[dict[int, int]]:
    tables = find_opname_tables(lib.read_bytes(), set(fmt.names))
    out = []
    for table in tables:
        fixed = {i: fmt.op[name] for i, name in enumerate(table.names) if name in fmt.op}
        out.append(fixed)
        print(f"opname table at file offset 0x{table.offset:x}: {len(table.names)} entries",
              file=sys.stderr)
    return out


def cmd_solve(args) -> int:
    loaded = _one_format(_load(args.paths))
    if not loaded:
        print("no Lua bytecode found", file=sys.stderr)
        return 1
    fmt = loaded[0][2].format
    chunks = [item.chunk for _, _, item in loaded]
    attempts: list[tuple[dict[int, int] | None, str]] = []
    if args.known:
        stock = [item.chunk for _, _, item in _load([args.known], quiet=True, prefer=fmt.name)
                 if item.format is fmt]
        known, matched = fmt.align(chunks, stock)
        print(f"known bytecode: {matched} function(s) matched, {len(known)} opcode(s) fixed",
              file=sys.stderr)
        if known:
            attempts.append((known, "known"))
    if args.lib:
        attempts.extend((fixed, "native") for fixed in _native_candidates(fmt, args.lib))
        if not attempts:
            print("no opname table found in the library; solving from bytecode only",
                  file=sys.stderr)
    attempts.append((None, "bytecode"))
    solution = None
    for fixed, source in attempts:
        try:
            solution = fmt.solve(chunks, fixed=fixed)
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
    data = {
        "format": MAP_FORMAT,
        "version": 1,
        "lua": fmt.name,
        "files": len(loaded),
        "header": fmt.header_info(loaded[0][2]),
        "ops": [r.to_dict(fmt.names) for r in sorted(solution.ops.values(), key=lambda r: r.game)],
        "ambiguous": [r.game for r in solution.ambiguous()],
    }
    text = json.dumps(data, indent=2)
    if args.output:
        args.output.write_text(text + "\n", "utf-8")
    else:
        print(text)
    _summary(fmt, solution, len(loaded))
    return 0


def _summary(fmt, solution, files: int) -> None:
    methods: dict[str, int] = {}
    for r in solution.ops.values():
        methods[r.method] = methods.get(r.method, 0) + 1
    parts = ", ".join(f"{n} by {m}" for m, n in sorted(methods.items()))
    print(f"{len(solution.ops)} {fmt.label} opcodes from {files} file(s): {parts}", file=sys.stderr)
    for r in solution.ambiguous():
        chosen = fmt.names[r.op] if r.op is not None else "?"
        others = [fmt.names[c] for c in r.candidates if c != r.op]
        listed = ", ".join(others[:3]) + (f" and {len(others) - 3} more" if len(others) > 3 else "")
        print(f"  low confidence: game {r.game} -> {chosen} (next best: {listed})", file=sys.stderr)


def _read_map(path: Path):
    data = json.loads(path.read_text("utf-8"))
    if data.get("format") != MAP_FORMAT:
        raise SystemExit(f"{path} is not an opsleuth map")
    fmt = FORMATS.get(data.get("lua", "5.1"))
    if fmt is None:
        raise SystemExit(f"{path}: unknown bytecode format {data.get('lua')!r}")
    return fmt, {int(op["game"]): fmt.op[op["op"]] for op in data["ops"] if op["op"]}


def cmd_apply(args) -> int:
    fmt, mapping = _read_map(args.map)
    loaded = [x for x in _load(args.paths, prefer=fmt.name) if x[2].format is fmt]
    failures = 0
    for _, rel, item in loaded:
        unknown = 0
        for fn in item.chunk.functions():
            code = []
            for ins in fn.code:
                if ins.op not in mapping:
                    unknown += 1
                code.append(ins.with_op(mapping.get(ins.op, ins.op)))
            fn.code = code
        target = args.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(fmt.dump(item))
        if unknown:
            failures += 1
            print(f"{rel}: {unknown} instruction(s) with unmapped opcodes", file=sys.stderr)
    print(f"wrote {len(loaded)} file(s) to {args.output}", file=sys.stderr)
    return 1 if failures else 0


def _decompile(command: list[str], path: Path) -> str | None:
    if "{}" in command:
        argv = [str(path) if part == "{}" else part for part in command]
    else:
        argv = [*command, str(path)]
    try:
        run = subprocess.run(argv, capture_output=True)
    except OSError as exc:
        return f"decompiler could not start: {exc}"
    if run.returncode != 0:
        return "decompiler failed: " + run.stderr.decode(errors="replace").strip()[:200]
    return None


def cmd_verify(args) -> int:
    bad = 0
    total = 0
    unluac = None
    if args.unluac:
        java = shutil.which("java")
        if java:
            unluac = [java, "-jar", str(Path(args.unluac)), "{}"]
        else:
            print("java not found; skipping the unluac check", file=sys.stderr)
    decompiler = shlex.split(args.decompiler) if args.decompiler else None
    for path, rel in _files(args.paths):
        total += 1
        data = path.read_bytes()
        fmt = sniff(data)
        try:
            chunk = fmt.strict_parse(data)
        except NotBytecode as exc:
            print(f"{rel}: cannot parse with a standard header ({exc})")
            bad += 1
            continue
        report = fmt.verify(chunk)
        problem = None if report.ok else report.problems[0]
        command = decompiler or (unluac if fmt.unluac else None)
        if problem is None and command:
            problem = _decompile(command, path)
        if problem:
            bad += 1
            print(f"{rel}: {problem}")
    print(f"{total - bad}/{total} file(s) passed", file=sys.stderr)
    return 1 if bad else 0


def cmd_scramble(args) -> int:
    fmt = None
    perm: dict[int, int] = {}
    for path, rel in _files(args.paths):
        try:
            item = load(path.read_bytes())
        except NotBytecode:
            continue
        if item.repairs:
            continue
        if fmt is None:
            fmt = item.format
            perm = fmt.permutation(args.seed)
        elif item.format is not fmt:
            continue
        target = args.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(fmt.scramble(item.chunk, perm, strip_debug=args.strip,
                                        damage_header=args.damage_header, seed=args.seed))
    if fmt is None:
        print("no stock bytecode found", file=sys.stderr)
        return 1
    if args.answer:
        answer = {"format": MAP_FORMAT, "version": 1, "lua": fmt.name,
                  "ops": [{"game": g, "op": fmt.names[s]} for s, g in sorted(perm.items())]}
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
                   help="stock compiler output for some of the same scripts")
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("apply", help="rewrite chunks to stock opcodes and header")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--map", type=Path, required=True)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("verify", help="check that chunks are consistent stock bytecode")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--unluac", help="path to unluac.jar for a Lua 5.1 decompiler check")
    p.add_argument("--decompiler", help=(
        "decompiler command run on every file, for example 'python ljd/main.py --file {}'; "
        "{} is replaced by the file path, or the path is appended"))
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
