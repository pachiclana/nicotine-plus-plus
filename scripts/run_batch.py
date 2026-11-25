#!/usr/bin/env python3
"""Interactive wrapper for the nicotine++ batch downloader.

Asks for the track-list JSON and output dir, makes sure the client's web API
is up (offers to start it), shows a dry-run, asks for confirmation, then runs
the real download. Resumable via <outdir>/_download_progress.json.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# Repo root = parent of this script's directory (scripts/..); override via env.
REPO = Path(os.environ.get("NICOTINE_REPO", Path(__file__).resolve().parent.parent))
PORT = int(os.environ.get("NICOTINE_WEB_API_PORT", "7770"))
BASE = f"http://127.0.0.1:{PORT}"
BATCH = Path(__file__).with_name("batch_download.py")
PY = sys.executable  # run everything with the interpreter that runs this script


def ask_path(prompt, default=""):
    while True:
        s = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip().strip('"')
        if not s and default:
            s = default
        p = Path(s).expanduser()
        if p.exists():
            return p
        print("  not found, try again")


def ask_dir(prompt, default=""):
    while True:
        s = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip().strip('"')
        if not s and default:
            s = default
        if s:
            return Path(s).expanduser()
        print("  required")


def api_up():
    try:
        return requests.get(f"{BASE}/foo", timeout=2).ok
    except Exception:
        return False


def start_client():
    print("Web API is down. Start the nicotine client headless? (Y/n)")
    if input("> ").strip().lower() in ("", "y", "yes"):
        print("starting client (background)...")
        subprocess.Popen([str(PY), "-m", "pynicotine", "--headless"], cwd=str(REPO),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            if api_up():
                print("web API is up.")
                return True
            time.sleep(2)
    return api_up()


def run(args, dry):
    cmd = [PY, str(BATCH), "--list", str(args["list"]), "--outdir", str(args["out"])]
    if dry:
        cmd.append("--dry-run")
    print(f"\n$ {' '.join(cmd)}\n")
    return subprocess.call(cmd)


def main():
    print("=== nicotine batch downloader ===")
    list_path = ask_path("Path of the track-list JSON")
    try:
        json.loads(list_path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        print(f"that file is not valid JSON ({e})"); return 1

    out = ask_dir("Output directory", str(list_path.parent / "downloads"))

    if not api_up() and not start_client():
        print("could not reach the web API on port", PORT); return 1

    args = {"list": list_path, "out": out}

    if input("\nDry-run first to preview picks? (y/N): ").strip().lower() in ("y", "yes"):
        print("\n--- DRY RUN (nothing is enqueued) ---")
        run(args, dry=True)
        print("\nProceed with the real download? (Y/n)")
        if input("> ").strip().lower() not in ("", "y", "yes"):
            print("Aborted. Re-run anytime; progress file makes it resumable.")
            return 0
    run(args, dry=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
