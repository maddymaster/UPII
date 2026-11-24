#!/usr/bin/env python3
"""Fetch the pinned memory-benchmarks harness and datasets into bench/memory/.cache/.

Everything comes from HARNESS.lock: the harness is cloned at the exact commit, and
each dataset is downloaded from a commit-pinned URL and checked against its SHA-256.
A mismatch is an error; nothing is used unverified. Only public code and public
datasets are downloaded; nothing is uploaded.

Usage:
    python bench/memory/fetch.py               # harness + LoCoMo
    python bench/memory/fetch.py --longmemeval # also LongMemEval-S (277 MB)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK_PATH = os.path.join(HERE, "HARNESS.lock")
CACHE = os.path.join(HERE, ".cache")
HARNESS_DIR = os.path.join(CACHE, "memory-benchmarks")
DATA_DIR = os.path.join(CACHE, "datasets")


def load_lock(path: str = LOCK_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _git(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def harness_commit(harness_dir: str = HARNESS_DIR) -> str | None:
    """HEAD of the fetched harness, or None if it is not there."""
    if not os.path.isdir(os.path.join(harness_dir, ".git")):
        return None
    return _git("rev-parse", "HEAD", cwd=harness_dir)


def fetch_harness(lock: dict, harness_dir: str = HARNESS_DIR) -> str:
    want = lock["harness"]["commit"]
    if harness_commit(harness_dir) is None:
        os.makedirs(os.path.dirname(harness_dir), exist_ok=True)
        _git("clone", "--quiet", lock["harness"]["repo"], harness_dir)
    if harness_commit(harness_dir) != want:
        _git("fetch", "--quiet", "origin", want, cwd=harness_dir)
        _git("checkout", "--quiet", "--detach", want, cwd=harness_dir)
    got = harness_commit(harness_dir)
    if got != want:
        raise SystemExit(f"harness at {got}, expected {want}")
    if _git("status", "--porcelain", cwd=harness_dir):
        raise SystemExit(f"harness checkout has local changes: {harness_dir}")
    return got


def verify_dataset(name: str, lock: dict, data_dir: str = DATA_DIR) -> str:
    """Path of the dataset file if present and matching its pinned SHA-256."""
    spec = lock["datasets"][name]
    path = os.path.join(data_dir, spec["file"])
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing; run bench/memory/fetch.py")
    got = sha256_file(path)
    if got != spec["sha256"]:
        raise ValueError(f"{path}: sha256 {got}, expected {spec['sha256']}")
    return path


def fetch_dataset(name: str, lock: dict, data_dir: str = DATA_DIR) -> str:
    spec = lock["datasets"][name]
    path = os.path.join(data_dir, spec["file"])
    try:
        return verify_dataset(name, lock, data_dir)
    except FileNotFoundError:
        pass
    os.makedirs(data_dir, exist_ok=True)
    tmp = path + ".part"
    print(f"downloading {name} ({spec['bytes']:,} bytes)")
    urllib.request.urlretrieve(spec["url"], tmp)
    got = sha256_file(tmp)
    if got != spec["sha256"]:
        os.remove(tmp)
        raise SystemExit(f"{name}: sha256 {got}, expected {spec['sha256']}")
    os.replace(tmp, path)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--longmemeval", action="store_true", help="also fetch LongMemEval-S (277 MB)")
    args = ap.parse_args(argv)
    lock = load_lock()
    print(f"harness {fetch_harness(lock)}")
    print(f"locomo  {fetch_dataset('locomo', lock)}")
    if args.longmemeval:
        print(f"longmemeval {fetch_dataset('longmemeval', lock)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
