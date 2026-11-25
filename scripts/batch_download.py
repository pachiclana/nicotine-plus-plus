#!/usr/bin/env python3
"""Batch-download tracks via the pachiclana nicotine++ web API.

Usage:
  python batch_download.py --list tracks.json --outdir D:/Music/inbox [--port 7770] [--dry-run]

Input JSON: a list of tracks. Accepted item shapes (keys case-insensitive):
  {"title": ..., "artists": [..]} | {"name"/"track": ..., "artist": ".."} | "Artist - Title"

Behavior:
- resume via <outdir>/_download_progress.json (buckets done/failed/no_result)
- per track: cleaned query (strip remix/feat suffixes, first artist),
  GET /search/global JSON body + smart_filters, enqueue best pick;
  recovery pass = artist-only search + client-side title-word filter
- polls /download/getdownloads, moves finished files from the client's
  downloaddir into --outdir (/download has no path parameter - files always
  land in transfers.downloaddir)
- --dry-run: search + report picks, enqueue nothing
"""
import argparse, json, re, shutil, time, unicodedata
from pathlib import Path
import requests

BASE = "http://127.0.0.1:{port}"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def clean_query(artist, title):
    title = re.sub(r"\((feat|ft|remix|extended|radio edit|original mix|club mix|mix)[^)]*\)", " ", title, flags=re.I)
    title = re.sub(r"\s*-\s*(feat|ft)\.?.*$", " ", title, flags=re.I)
    return " ".join(x for x in (re.split(r",|&", artist)[0].strip(), title.strip()) if x)


def parse_items(raw):
    items = []
    for it in raw:
        if isinstance(it, str):
            if " - " in it:
                a, t = it.split(" - ", 1)
                items.append({"artist": a.strip(), "title": t.strip()})
            else:
                items.append({"artist": "", "title": it.strip()})
            continue
        low = {k.lower(): v for k, v in it.items()}
        artist = low.get("artist") or (low.get("artists") or [None])[0]
        if isinstance(artist, dict):
            artist = artist.get("name", "")
        title = low.get("title") or low.get("name") or low.get("track") or ""
        items.append({"artist": str(artist or ""), "title": str(title)})
    return items


def search(base, term, wait=15, smart=True):
    r = requests.get(f"{base}/search/global",
                     json={"search_term": term, "wait_for_seconds": wait, "smart_filters": smart}, timeout=wait + 30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json().get("results", []) or []


def pick(results, artist, title):
    if not results:
        return None
    a, t = norm(artist), norm(title)
    words = [w for w in t.split() if len(w) > 2]
    def ok(r):
        fn = norm(Path(r.get("file_path", "")).name)
        return (not a or a.split()[0] in fn) and sum(w in fn for w in words) >= max(1, len(words) - 1)
    good = [r for r in results if ok(r)] or results
    good.sort(key=lambda r: (-int(r.get("bitrate") or 0), -r.get("search_similarity", 0)))
    return good[0]


def enqueue(base, res):
    r = requests.get(f"{base}/download", json={"file_owner": res["user"],
                                              "file_virtual_path": res["file_path"]}, timeout=30)
    r.raise_for_status()


def wait_finished(base, want_paths, timeout=3600):
    done = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            transfers = requests.get(f"{base}/download/getdownloads", timeout=30).json()
        except Exception:
            time.sleep(5); continue
        pending = False
        for tr in transfers:
            vp = tr.get("virtual_path", "")
            if vp not in want_paths:
                continue
            st = (tr.get("status") or "").lower()
            if st in ("finished", "completed", "done"):
                done[vp] = tr.get("download_path")
            elif st in ("failed", "aborted", "cancelled"):
                done[vp] = None
            else:
                pending = True
        if not pending and all(vp in done for vp in want_paths):
            break
        time.sleep(5)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--port", type=int, default=7770)
    ap.add_argument("--wait", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    base = BASE.format(port=args.port)
    assert requests.get(f"{base}/foo", timeout=5).ok, "web API not up - start the client first"

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    prog_path = outdir / "_download_progress.json"
    prog = json.loads(prog_path.read_text()) if prog_path.exists() else {"done": {}, "failed": {}, "no_result": {}}

    items = parse_items(json.loads(Path(args.list).read_text(encoding="utf-8-sig")))
    print(f"{len(items)} tracks in list")

    enqueued = []
    for i, it in enumerate(items, 1):
        key = f"{it['artist']} - {it['title']}"
        if key in prog["done"]:
            print(f"[{i}] skip (done): {key}"); continue
        term = clean_query(it["artist"], it["title"])
        try:
            res = pick(search(base, term, args.wait), it["artist"], it["title"])
            if not res and it["artist"]:
                res = pick(search(base, it["artist"], args.wait), it["artist"], it["title"])
        except Exception as e:
            print(f"[{i}] ERROR {key}: {e}"); prog["failed"][key] = str(e); continue
        if not res:
            print(f"[{i}] no result: {key}"); prog["no_result"][key] = term; continue
        print(f"[{i}] {key} <- {res['user']} | {Path(res['file_path']).name} ({res.get('bitrate')}kbps)")
        if not args.dry_run:
            enqueue(base, res)
            prog["done"][key] = res["file_path"]
            enqueued.append(res["file_path"])
        prog_path.write_text(json.dumps(prog, indent=1))
        time.sleep(1)

    if enqueued and not args.dry_run:
        print("waiting for transfers...")
        finished = wait_finished(base, set(enqueued))
        for vp, folder in finished.items():
            if not folder:
                continue
            src = Path(folder) / Path(vp).name
            if src.exists():
                shutil.move(str(src), str(outdir / src.name))
                print(f"moved {src.name}")
    prog_path.write_text(json.dumps(prog, indent=1))
    print(json.dumps({k: len(v) for k, v in prog.items()}))


if __name__ == "__main__":
    main()
