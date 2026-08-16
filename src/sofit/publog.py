"""`sofit publish-log` - record a posted clip at publish time.

Creates the attribution join key (clip <-> hook variant <-> platform <-> post
URL) that the metrics scraper fills in later. Rows append to the same
performance log the clip selector learns from (`generate.PERF_LOG`); a row
written here carries no metrics yet, which is safe by construction -
`generate._perf_rows()` only counts rows that already have views/retention.

Usage:
    sofit publish-log clips/clip-5.mp4 --episode WS205 --platform tiktok \
        --url https://www.tiktok.com/@show/video/123
    sofit publish-log clip-5.hook1.mp4 --episode WS205 --platform instagram \
        --url https://www.instagram.com/reel/abc/ --spec ep.clips.json

The hook variant is inferred from the rendered filename (the renderer encodes
it): `clip-5.mp4` = primary hook (variant 0), `clip-5.hookN.mp4` = variant N.
The hook TEXT comes from the clips.json spec (--spec, or auto-discovered next
to the file), or --hook as an override.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _clip_and_variant(name: str) -> tuple[str, int]:
    """`clip-5` -> (clip-5, 0); `clip-5.hook2.mp4` -> (clip-5, 2)."""
    stem = Path(name).name
    stem = re.sub(r"\.mp4$", "", stem)
    m = re.match(r"^(.*?)\.hook(\d+)$", stem)
    return (m.group(1), int(m.group(2))) if m else (stem, 0)


def _duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=15)
        return round(float(out.stdout.strip()), 2)
    except Exception:  # noqa: BLE001 - duration is best-effort
        return None


def _hook_from_spec(spec_path: Path, clip_id: str, variant: int) -> str | None:
    try:
        doc = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for c in doc.get("clips", []):
        if str(c.get("id")) == clip_id:
            if variant == 0:
                return c.get("hook")
            alts = c.get("hook_variants") or []
            return alts[variant - 1] if variant <= len(alts) else c.get("hook")
    return None


def _hook_near_file(clip_file: Path, clip_id: str, variant: int) -> str | None:
    """Search every *.clips.json near the rendered file; the spec that actually
    CONTAINS this clip id wins (a directory can hold several batches' specs)."""
    for d in (clip_file.parent, clip_file.parent.parent):
        if not d.exists():
            continue
        # *.clips*.json also catches versioned specs like ep.clips2.json
        for spec in sorted(d.glob("*.clips*.json")):
            hook = _hook_from_spec(spec, clip_id, variant)
            if hook:
                return hook
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sofit publish-log",
        description="Record a posted clip so metrics can be attributed to it.")
    p.add_argument("clip", help="rendered clip file (or bare clip id like clip-5 / clip-5.hook1)")
    p.add_argument("--episode", required=True, help="episode label, e.g. WS205")
    p.add_argument("--platform", required=True,
                   choices=["tiktok", "instagram", "youtube"])
    p.add_argument("--url", required=True, help="the live post URL")
    p.add_argument("--spec", help="clips.json spec (default: auto-discover next to the file)")
    p.add_argument("--hook", help="hook text override (else read from the spec)")
    p.add_argument("--log", help="performance log path (default: sofit's PERF_LOG)")
    args = p.parse_args(argv)

    from . import generate  # lazy: keeps --help fast

    clip_id, variant = _clip_and_variant(args.clip)
    clip_path = Path(args.clip)

    hook = args.hook
    if not hook and args.spec:
        hook = _hook_from_spec(Path(args.spec), clip_id, variant)
    if not hook and clip_path.exists():
        hook = _hook_near_file(clip_path, clip_id, variant)
    if not hook:
        print("error: hook text not found - pass --spec or --hook", file=sys.stderr)
        return 1

    row: dict = {
        "date": datetime.date.today().isoformat(),
        "episode": args.episode, "clip": clip_id, "variant": variant,
        "platform": args.platform, "hook": hook, "post_url": args.url,
    }
    if clip_path.exists():
        dur = _duration(clip_path)
        if dur:
            row["duration"] = dur

    log_path = args.log or generate.PERF_LOG
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    # Duplicate guard: same URL already logged -> refuse (re-posting is a new URL).
    try:
        for line in Path(log_path).read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("post_url") == args.url:
                print(f"error: {args.url} already logged", file=sys.stderr)
                return 1
    except FileNotFoundError:
        pass
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    rows = generate._perf_rows(log_path)
    need = max(0, generate.MIN_PERF_ROWS - len(rows))
    print(f"logged {clip_id} (variant {variant}, {args.platform}) -> {log_path}")
    print(f"metrics pending (the scraper fills them at T+3d); "
          f"{need} more attributed row(s) until pool generation learns from data.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
