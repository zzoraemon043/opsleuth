from pathlib import Path

from .. import model
from .chunk import parse
from .features import FAMILIES, extract
from .opcodes import NAMES


class Model(model.Model):
    names = NAMES
    families = FAMILIES
    package = __package__
    extract = staticmethod(extract)


train = Model.train


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="train the Lua 5.1 opcode model")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    chunks = []
    for root in args.inputs:
        files = sorted(root.rglob("*")) if root.is_dir() else [root]
        chunks.extend(parse(f.read_bytes()) for f in files if f.is_file())
    args.output.write_text(train(chunks).to_json(), "utf-8")


if __name__ == "__main__":
    main()
