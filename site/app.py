import io
import json
import zipfile
from pathlib import Path

from opsleuth.formats import NotBytecode, load
from opsleuth.solver import Contradiction


def _load_dir(root: Path):
    loaded = []
    skipped = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            loaded.append((path.relative_to(root), load(path.read_bytes())))
        except NotBytecode:
            skipped.append(str(path.relative_to(root)))
    return loaded, skipped


def analyse(root: str, archive_path: str = "/tmp/restored.zip") -> str:
    loaded, skipped = _load_dir(Path(root))
    if not loaded:
        return json.dumps({"error": "No Lua 5.1 or LuaJIT 2.1 bytecode found.", "skipped": skipped})
    counts: dict[str, int] = {}
    for _, item in loaded:
        counts[item.format.name] = counts.get(item.format.name, 0) + 1
    main = max(counts, key=counts.get)
    loaded = [x for x in loaded if x[1].format.name == main]
    fmt = loaded[0][1].format
    try:
        solution = fmt.solve([item.chunk for _, item in loaded])
    except Contradiction as exc:
        return json.dumps({"error": f"No consistent mapping: {exc}"})
    flagged = {r.game for r in solution.ambiguous()}
    ops = []
    for r in sorted(solution.ops.values(), key=lambda r: (r.game not in flagged, r.game)):
        ops.append({
            "game": r.game,
            "op": fmt.names[r.op] if r.op is not None else None,
            "method": r.method,
            "margin": None if r.margin is None or r.margin == float("inf") else round(r.margin, 1),
            "count": r.count,
            "low": r.game in flagged,
            "next": [fmt.names[c] for c in r.candidates if c != r.op][:3],
        })
    mapping = solution.mapping
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, item in loaded:
            for fn in item.chunk.functions():
                fn.code = [ins.with_op(mapping.get(ins.op, ins.op)) for ins in fn.code]
            archive.writestr(str(rel).replace("\\", "/"), fmt.dump(item))
        archive.writestr("map.json", json.dumps({
            "format": "opsleuth-map", "version": 1, "lua": fmt.name,
            "ops": [{"game": o["game"], "op": o["op"], "method": o["method"]} for o in ops],
        }, indent=2))
    Path(archive_path).write_bytes(buffer.getvalue())
    files = [{"name": str(rel), "format": fmt.describe(item),
              "repairs": item.repairs} for rel, item in loaded]
    return json.dumps({
        "format": fmt.label, "files": files, "skipped": skipped,
        "ignored": sum(counts.values()) - len(loaded), "ops": ops,
    })
