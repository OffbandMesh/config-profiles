#!/usr/bin/env python3
"""Validate the radio preset files in radio-presets/.

    python scripts/validate_radio_presets.py            # both files
    python scripts/validate_radio_presets.py --overlay radio-presets/offband.json
    python scripts/validate_radio_presets.py --upstream radio-presets/meshcore-upstream.json

Exit 0 when every file checked is valid, 1 with one line per problem otherwise.
Standard library only, so CI needs no installs. The rules are in SCHEMA.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "radio-presets" / "offband.json"
UPSTREAM = ROOT / "radio-presets" / "meshcore-upstream.json"

OVERLAY_FORMAT = "offband-radio-presets"
UPSTREAM_FORMAT = "meshcore-upstream-radio-presets"
FORMAT_VERSION = 1

# LoRa bandwidths, in kHz, that MeshCore radios accept.
BANDWIDTHS = (7.8, 10.4, 15.6, 20.8, 31.25, 41.7, 62.5, 125, 250, 500)
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

OVERLAY_KEYS = {"id", "title", "region", "frequency", "bandwidth", "spreading_factor", "coding_rate",
                "tx_power", "path_hash_size", "off_grid", "overrides_upstream", "status", "notes"}
OVERLAY_REQUIRED = {"id", "title", "region", "frequency", "bandwidth", "spreading_factor",
                    "coding_rate", "status"}
UPSTREAM_ENTRY_KEYS = {"title", "description", "frequency", "spreading_factor", "bandwidth",
                       "coding_rate", "network_settings"}
UPSTREAM_ENTRY_REQUIRED = {"title", "frequency", "spreading_factor", "bandwidth", "coding_rate"}


def _num(v):
    """A JSON number, or a numeric string (the upstream API sends strings)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None and n == int(n) else None


def check_radio(where, freq, bw, sf, cr, problems):
    f = _num(freq)
    if f is None or not 150 <= f <= 2500:
        problems.append(f"{where}: frequency {freq!r} must be a number of MHz, 150-2500")
    b = _num(bw)
    if b is None or not any(abs(b - x) < 1e-6 for x in BANDWIDTHS):
        problems.append(f"{where}: bandwidth {bw!r} must be one of {', '.join(str(x) for x in BANDWIDTHS)} kHz")
    s = _int(sf)
    if s is None or not 5 <= s <= 12:
        problems.append(f"{where}: spreading_factor {sf!r} must be a whole number 5-12")
    c = _int(cr)
    if c is None or not 5 <= c <= 8:
        problems.append(f"{where}: coding_rate {cr!r} must be the 4/x denominator, a whole number 5-8")


def check_path_hash(where, v, problems):
    h = _int(v)
    if h is None or not 1 <= h <= 3:
        problems.append(f"{where}: path_hash_size {v!r} must be a whole number of bytes, 1-3")


def validate_upstream(doc, problems):
    """Checks the mirror file. Returns the set of upstream titles (for override checks)."""
    titles = set()
    if not isinstance(doc, dict):
        problems.append("upstream: top level must be a JSON object")
        return titles
    if doc.get("format") != UPSTREAM_FORMAT:
        problems.append(f"upstream: format must be {UPSTREAM_FORMAT!r}")
    if doc.get("format_version") != FORMAT_VERSION:
        problems.append(f"upstream: format_version must be {FORMAT_VERSION}")
    for key in ("source", "credit", "updated_at"):
        if not isinstance(doc.get(key), str) or not doc.get(key):
            problems.append(f"upstream: {key} is required")
    srs = doc.get("suggested_radio_settings")
    if not isinstance(srs, dict):
        problems.append("upstream: suggested_radio_settings must be an object")
        return titles
    entries = srs.get("entries")
    if not isinstance(entries, list) or not entries:
        problems.append("upstream: suggested_radio_settings.entries must be a non-empty list")
        return titles
    for i, e in enumerate(entries):
        where = f"upstream entry {i}"
        if not isinstance(e, dict):
            problems.append(f"{where}: must be an object")
            continue
        where = f"upstream entry {i} ({e.get('title')!r})"
        unknown = set(e) - UPSTREAM_ENTRY_KEYS
        if unknown:
            problems.append(f"{where}: unknown keys {sorted(unknown)} (the upstream shape changed)")
        missing = UPSTREAM_ENTRY_REQUIRED - set(e)
        if missing:
            problems.append(f"{where}: missing {sorted(missing)}")
            continue
        if not isinstance(e["title"], str) or not e["title"].strip():
            problems.append(f"{where}: title must be a non-empty string")
        elif e["title"] in titles:
            problems.append(f"{where}: duplicate title")
        else:
            titles.add(e["title"])
        check_radio(where, e["frequency"], e["bandwidth"], e["spreading_factor"], e["coding_rate"], problems)
        ns = e.get("network_settings")
        if ns is not None:
            if not isinstance(ns, dict) or set(ns) - {"path_hash_size"}:
                problems.append(f"{where}: network_settings may only carry path_hash_size")
            elif "path_hash_size" in ns:
                check_path_hash(where, ns["path_hash_size"], problems)
    return titles


def validate_overlay(doc, upstream_titles, problems):
    if not isinstance(doc, dict):
        problems.append("overlay: top level must be a JSON object")
        return
    if doc.get("format") != OVERLAY_FORMAT:
        problems.append(f"overlay: format must be {OVERLAY_FORMAT!r}")
    if doc.get("format_version") != FORMAT_VERSION:
        problems.append(f"overlay: format_version must be {FORMAT_VERSION}")
    presets = doc.get("presets")
    if not isinstance(presets, list):
        problems.append("overlay: presets must be a list")
        return
    ids, titles = set(), set()
    for i, p in enumerate(presets):
        where = f"overlay entry {i}"
        if not isinstance(p, dict):
            problems.append(f"{where}: must be an object")
            continue
        where = f"overlay entry {i} ({p.get('id')!r})"
        unknown = set(p) - OVERLAY_KEYS
        if unknown:
            problems.append(f"{where}: unknown keys {sorted(unknown)}")
        missing = OVERLAY_REQUIRED - set(p)
        if missing:
            problems.append(f"{where}: missing {sorted(missing)}")
            continue
        if not isinstance(p["id"], str) or not ID_RE.match(p["id"]):
            problems.append(f"{where}: id must be lowercase letters, digits and single hyphens")
        elif p["id"] in ids:
            problems.append(f"{where}: duplicate id")
        else:
            ids.add(p["id"])
        title = p["title"]
        if not isinstance(title, str) or not title.strip():
            problems.append(f"{where}: title must be a non-empty string")
        elif title in titles:
            problems.append(f"{where}: duplicate title")
        else:
            titles.add(title)
        if not isinstance(p["region"], str) or not p["region"].strip():
            problems.append(f"{where}: region must be a non-empty string")
        for key in ("frequency", "bandwidth", "spreading_factor", "coding_rate"):
            if isinstance(p[key], str):
                problems.append(f"{where}: {key} must be a JSON number, not a string")
        check_radio(where, p["frequency"], p["bandwidth"], p["spreading_factor"], p["coding_rate"], problems)
        if "tx_power" in p:
            t = p["tx_power"]
            if isinstance(t, bool) or not isinstance(t, int) or not -9 <= t <= 30:
                problems.append(f"{where}: tx_power {t!r} must be a whole number of dBm, -9 to 30")
        if "path_hash_size" in p:
            h = p["path_hash_size"]
            if isinstance(h, bool) or not isinstance(h, int):
                problems.append(f"{where}: path_hash_size must be a JSON number, not {type(h).__name__}")
            else:
                check_path_hash(where, h, problems)
        for key in ("off_grid", "overrides_upstream"):
            if key in p and not isinstance(p[key], bool):
                problems.append(f"{where}: {key} must be true or false")
        if p["status"] not in ("published", "retired"):
            problems.append(f"{where}: status must be 'published' or 'retired'")
        if "notes" in p and not isinstance(p["notes"], str):
            problems.append(f"{where}: notes must be a string")
        if upstream_titles is not None and isinstance(title, str):
            marked = p.get("overrides_upstream") is True
            if title in upstream_titles and not marked:
                problems.append(f"{where}: title {title!r} is also in the upstream list; "
                                "set overrides_upstream: true if replacing it is deliberate")
            if marked and title not in upstream_titles:
                problems.append(f"{where}: overrides_upstream is set but no upstream entry is titled {title!r}")


def load(path, problems):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"{path}: not found")
    except ValueError as e:
        problems.append(f"{path}: not valid JSON ({e})")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--overlay", help="overlay file to check (default: radio-presets/offband.json)")
    ap.add_argument("--upstream", help="mirror file to check (default: radio-presets/meshcore-upstream.json)")
    args = ap.parse_args(argv)
    both = args.overlay is None and args.upstream is None
    overlay_path = args.overlay or (OVERLAY if both else None)
    upstream_path = args.upstream or (UPSTREAM if both or args.overlay else None)

    problems = []
    upstream_titles = None
    if upstream_path:
        doc = load(upstream_path, problems)
        if doc is not None:
            upstream_titles = validate_upstream(doc, problems)
    if overlay_path:
        doc = load(overlay_path, problems)
        if doc is not None:
            validate_overlay(doc, upstream_titles, problems)

    for p in problems:
        print(f"INVALID: {p}")
    if problems:
        print(f"{len(problems)} problem(s).")
        return 1
    checked = ", ".join(str(p) for p in (upstream_path, overlay_path) if p)
    print(f"OK: {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
