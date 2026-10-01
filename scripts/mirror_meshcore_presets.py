#!/usr/bin/env python3
"""Mirror MeshCore's suggested radio presets into radio-presets/meshcore-upstream.json.

    python scripts/mirror_meshcore_presets.py                 # fetch from the API
    python scripts/mirror_meshcore_presets.py --from-file x   # use a saved response (tests)

The source is the public preset list maintained by Liam Cottle for MeshCore, the
same list the stock MeshCore app shows. It is copied unmodified, with a header that
credits the source.

Exit codes:
  0  mirror unchanged, or updated (prints which)
  1  fetch failed, the response isn't valid, or the presets fail validation.
     Nothing is written, so the last good mirror stays in place.
Standard library only.
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_radio_presets as v  # noqa: E402

SOURCE = "https://api.meshcore.nz/api/v1/config"
CREDIT = ("Radio presets maintained by Liam Cottle for MeshCore (meshcore.nz), the list "
          "the stock MeshCore app shows. Mirrored unmodified from " + SOURCE + ". "
          "Offband's own additions live in offband.json.")
USER_AGENT = "offband-config-profiles-mirror (+https://github.com/OffbandMesh/config-profiles)"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return resp.read().decode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-file", help="read the API response from a file instead of fetching")
    ap.add_argument("--out", default=str(v.UPSTREAM), help="mirror file to write")
    args = ap.parse_args(argv)

    try:
        raw = Path(args.from_file).read_text(encoding="utf-8") if args.from_file else fetch(SOURCE)
        api = json.loads(raw)
    except Exception as e:  # any fetch or parse failure fails the run loudly
        print(f"FAILED: could not read the preset list from {args.from_file or SOURCE}: {e}")
        return 1

    srs = api.get("config", {}).get("suggested_radio_settings") if isinstance(api, dict) else None
    if not isinstance(srs, dict):
        print("FAILED: the response has no config.suggested_radio_settings object (the upstream shape changed)")
        return 1

    out = Path(args.out)
    old = None
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except ValueError:
            old = None
    if isinstance(old, dict) and old.get("suggested_radio_settings") == srs:
        print(f"UNCHANGED: {len(srs.get('entries') or [])} presets, nothing to write")
        return 0

    doc = {
        "format": v.UPSTREAM_FORMAT,
        "format_version": v.FORMAT_VERSION,
        "source": SOURCE,
        "credit": CREDIT,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suggested_radio_settings": srs,
    }
    problems = []
    v.validate_upstream(doc, problems)
    if problems:
        for p in problems:
            print(f"INVALID: {p}")
        print(f"FAILED: {len(problems)} problem(s); the mirror was not updated")
        return 1

    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"UPDATED: {len(srs['entries'])} presets written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
