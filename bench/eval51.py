import argparse
import random
import sys
import time
from pathlib import Path

from opsleuth.lua51.chunk import parse
from opsleuth.lua51.model import train
from opsleuth.lua51.opcodes import NAMES
from opsleuth.lua51.scramble import random_permutation, remap, strip
from opsleuth.lua51.solve import solve


def project_of(path: Path) -> str:
    return path.name.split("_")[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--sizes", default="5,20,50,200")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--strip", action="store_true")
    args = parser.parse_args()
    files = sorted(args.corpus.glob("*.luac"))
    projects = sorted({project_of(f) for f in files})
    for held in projects:
        test = [f for f in files if project_of(f) == held]
        model = train([parse(f.read_bytes()) for f in files if project_of(f) != held])
        for size in [int(s) for s in args.sizes.split(",")]:
            if size > len(test) and size != int(args.sizes.split(",")[0]):
                continue
            correct = total = 0
            wrong: dict[str, int] = {}
            started = time.time()
            for trial in range(args.trials):
                rng = random.Random(trial)
                sample = rng.sample(test, min(size, len(test)))
                perm = random_permutation(trial)
                chunks = []
                for f in sample:
                    chunk = parse(f.read_bytes())
                    remap(chunk, perm)
                    if args.strip:
                        strip(chunk)
                    chunks.append(chunk)
                inverse = {g: s for s, g in perm.items()}
                solution = solve(chunks, model)
                for g, result in solution.ops.items():
                    total += 1
                    if result.op == inverse[g]:
                        correct += 1
                    else:
                        key = f"{NAMES[inverse[g]]}->{NAMES[result.op] if result.op is not None else None}"
                        wrong[key] = wrong.get(key, 0) + 1
            elapsed = (time.time() - started) / args.trials
            print(f"{held:14} files={min(size, len(test)):4} acc={correct}/{total} {elapsed:5.1f}s {wrong}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
