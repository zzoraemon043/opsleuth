import argparse
import random
import sys
import time
from pathlib import Path

from opsleuth.luajit.bytecode import parse
from opsleuth.luajit.model import train
from opsleuth.luajit.scramble import random_permutation, remap, strip
from opsleuth.luajit.solve import solve


def project_of(path: Path) -> str:
    return path.name.split("_")[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--test", type=Path, help="files to solve; defaults to the corpus")
    parser.add_argument("--sizes", default="10,20,50,100,100000")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--strip", action="store_true")
    args = parser.parse_args()
    files = sorted(args.corpus.rglob("*.ljbc"))
    tests = sorted((args.test or args.corpus).rglob("*.ljbc"))
    projects = sorted({project_of(f) for f in tests})
    for held in projects:
        test = [f for f in tests if project_of(f) == held]
        model = train([parse(f.read_bytes()) for f in files if project_of(f) != held])
        for size in [int(s) for s in args.sizes.split(",")]:
            correct = total = flagged_wrong = 0
            started = time.time()
            for trial in range(args.trials):
                rng = random.Random(trial)
                sample = rng.sample(test, min(size, len(test)))
                perm = random_permutation(trial)
                dumps = []
                for f in sample:
                    d = parse(f.read_bytes())
                    remap(d, perm)
                    if args.strip:
                        strip(d)
                    dumps.append(d)
                inverse = {g: s for s, g in perm.items()}
                solution = solve(dumps, model)
                flagged = {r.game for r in solution.ambiguous()}
                for g, result in solution.ops.items():
                    total += 1
                    if result.op == inverse[g]:
                        correct += 1
                    elif g in flagged:
                        flagged_wrong += 1
            elapsed = (time.time() - started) / args.trials
            wrong = total - correct
            print(f"{held:20} files={min(size, len(test)):5} wrong={wrong}/{total} "
                  f"flagged={flagged_wrong}/{wrong} {elapsed:5.1f}s")
            sys.stdout.flush()
            if size >= len(test):
                break


if __name__ == "__main__":
    main()
