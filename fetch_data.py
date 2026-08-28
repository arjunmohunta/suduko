"""
fetch_data.py -- download the public benchmark sets used in the evaluation.

The small sets live in puzzles/ and are committed to the repository. The large
sets are several megabytes, so they are downloaded into data/ on demand and
excluded from version control; this script makes that step reproducible.

Usage:  python3 fetch_data.py           # fetch anything missing
        python3 fetch_data.py --force   # re-download everything
"""
from __future__ import annotations

import argparse
import io
import os
import urllib.request
import zipfile

# Small, directly-linkable sets -> puzzles/ (committed).
SMALL = [
    ("puzzles/top95.txt", "https://norvig.com/top95.txt",
     "95 hard puzzles, collected by Peter Norvig"),
    ("puzzles/hardest11.txt", "https://norvig.com/hardest.txt",
     "11 'hardest' puzzles, collected by Peter Norvig"),
]

# Large sets ship inside the tdoku benchmark archive -> data/ (not committed).
TDOKU_ZIP = "https://raw.githubusercontent.com/t-dillon/tdoku/master/data.zip"
FROM_ZIP = [
    ("data/kaggle100k.txt", "data/puzzles0_kaggle",
     "100,000-puzzle export of the Kaggle '1 million Sudoku games' set"),
    ("data/minimal17.txt", "data/puzzles2_17_clue",
     "49,158 minimal 17-clue puzzles (Royle's collection, extended)"),
    ("data/top1465.txt", "data/puzzles3_magictour_top1465",
     "1,465 hard puzzles (magictour 'top1465')"),
    ("data/forum_hardest1106.txt", "data/puzzles6_forum_hardest_1106",
     "forum-curated 'hardest' collection"),
]

UA = {"User-Agent": "cs175-sudoku-benchmark/1.0"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def count_grids(path: str) -> int:
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                if sum(1 for ch in line if ch in "0123456789.") == 81:
                    n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download existing files")
    args = ap.parse_args()

    os.makedirs("puzzles", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    for dest, url, desc in SMALL:
        if os.path.exists(dest) and not args.force:
            print(f"  have  {dest:<32} {count_grids(dest):>7,} puzzles")
            continue
        print(f"  get   {dest:<32} <- {url}")
        with open(dest, "wb") as fh:
            fh.write(get(url))
        print(f"        {count_grids(dest):,} puzzles  ({desc})")

    need_zip = [d for d, _, _ in FROM_ZIP if not os.path.exists(d)] or args.force
    if not need_zip:
        for dest, _, _ in FROM_ZIP:
            print(f"  have  {dest:<32} {count_grids(dest):>7,} puzzles")
        print("\nall benchmark sets present.")
        return

    print(f"\n  get   tdoku benchmark archive  <- {TDOKU_ZIP}")
    blob = get(TDOKU_ZIP)
    print(f"        {len(blob) / 1e6:.1f} MB downloaded, extracting the sets we use")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = set(zf.namelist())
        for dest, member, desc in FROM_ZIP:
            if os.path.exists(dest) and not args.force:
                print(f"  have  {dest:<32} {count_grids(dest):>7,} puzzles")
                continue
            if member not in names:
                print(f"  MISS  {member} not in archive -- skipping {dest}")
                continue
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
            print(f"        {dest:<32} {count_grids(dest):>7,} puzzles  ({desc})")

    print("\nall benchmark sets present.")


if __name__ == "__main__":
    main()
