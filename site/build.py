import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from opsleuth.cli import main as cli

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def _zip_dir(folder: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(folder.parent if folder.name == "opsleuth" else folder))


def build(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    (out / "samples").mkdir(parents=True)
    for name in ("index.html", "app.py"):
        shutil.copy(SITE / name, out / name)
    _zip_dir(ROOT / "opsleuth", out / "opsleuth.zip")
    with tempfile.TemporaryDirectory() as tmp:
        for name, source in (("lua51", "luac51"), ("luajit", "luajit")):
            game = Path(tmp) / name
            code = cli(["scramble", str(ROOT / "tests" / "data" / source), "-o", str(game),
                        "--seed", "2026", "--strip", "--damage-header"])
            if code:
                raise SystemExit(f"could not build the {name} sample")
            _zip_dir(game, out / "samples" / f"{name}.zip")
    (out / ".nojekyll").write_text("")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site")
