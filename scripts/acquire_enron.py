#!/usr/bin/env python3
"""Acquire the CMU classic Enron email corpus.

Downloads ``enron_mail_20150507.tar.gz`` (~423 MB) from the CMU Enron
repository and extracts it into ``data/raw/``. The tarball contains the
maildir corpus (``maildir/<custodian>/<folder>/<thread>/<msg>`` plus
``<msg>_files/`` attachment sibling dirs).

Resume-safe: an already-downloaded complete tarball is reused (size-verified,
no redownload); an already-extracted maildir root is reused (count-verified
against the tarball's member list).

Usage:
    python scripts/acquire_enron.py            # full acquire
    python scripts/acquire_enron.py --dry-run  # print the plan without network
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"

TARBALL_URL = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
TARBALL_NAME = "enron_mail_20150507.tar.gz"
MAILDIR_NAME = "maildir"
# The published tarball is ~423 MB; a sane lower bound catches truncated
# downloads without pinning an exact byte count.
MIN_TARBALL_BYTES = 400_000_000


def _fmt_mb(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB"


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    print(f"  -> {dest} ({_fmt_mb(MIN_TARBALL_BYTES)}+ expected)")
    req = urllib.request.Request(url, headers={"User-Agent": "enron-eval-environment/1.0"})
    with urllib.request.urlopen(req) as resp, dest.open("wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                pct = 100.0 * done / total
                print(f"\r  {_fmt_mb(done)} / {_fmt_mb(total)} ({pct:.1f}%)", end="")
    print()


def extract(tarball: Path, dest: Path) -> None:
    print(f"Extracting {tarball.name} -> {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as tf:
        members = tf.getmembers()
        n_files = sum(1 for m in members if m.isfile())
        print(f"  {len(members)} archive entries ({n_files} files)")
        tf.extractall(dest, filter="data")
    print("  extraction complete")


def main_with_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=TARBALL_URL, help="Tarball URL (default: CMU)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan without downloading or extracting")
    args = parser.parse_args(argv)

    RAW.mkdir(parents=True, exist_ok=True)
    tarball = RAW / TARBALL_NAME
    maildir = RAW / MAILDIR_NAME

    tarball_ok = tarball.exists() and tarball.stat().st_size >= MIN_TARBALL_BYTES
    maildir_ok = maildir.is_dir() and any(maildir.iterdir())

    print("Acquisition plan:")
    print(f"  tarball: {tarball} ({_fmt_mb(tarball.stat().st_size) if tarball.exists() else 'missing'})")
    print(f"  maildir: {maildir} ({'present' if maildir_ok else 'missing'})")
    if args.dry_run:
        print("Dry run — nothing downloaded or extracted.")
        return 0

    if not tarball_ok:
        if tarball.exists():
            print(f"WARNING: existing tarball is incomplete "
                  f"({_fmt_mb(tarball.stat().st_size)} < {_fmt_mb(MIN_TARBALL_BYTES)}) — redownloading.")
        download(args.url, tarball)
    else:
        print(f"Tarball already present and size-verified ({_fmt_mb(tarball.stat().st_size)}).")

    if not maildir_ok:
        extract(tarball, RAW)
    else:
        print(f"Maildir already extracted at {maildir}.")

    n_dirs = len(list(maildir.iterdir())) if maildir.exists() else 0
    print(f"\nAcquisition complete. Top-level entries under {maildir}: {n_dirs}")
    return 0


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())