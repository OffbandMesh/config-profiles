# Config-profile & catalog schema

Two file types live here: **profile YAMLs** (the actual config a device applies)
and a **catalog manifest** (`profiles.json`) that lists them.

## Profile YAML (v2 — capability sections)

A profile is a set of **capability-scoped sections**. A device applies the
sections it supports; the schema of each section is shared by every device with
that capability. (v1's flat layout is no longer accepted — use `schema_version: 2`.)

```yaml
schema_version: 2          # required; must be 2
name: US wide-area         # optional label, shown in the app; not applied

wifi:                      # section: any wifi-capable device
  ssid: my-net
  password: secret         # write-only on device; avoid in shared profiles
  enabled: true

mqtt:                      # section: observer/MQTT capability
  region: IAD              # -> mqtt.iata (per-location; see note below)
  status_interval: 60      # seconds, >= 0
  brokers:                 # slots 0..5
    - slot: 0              # required per entry, 0..5, unique
      # NOTE: broker `enabled` is NOT a profile field — enabling a broker is the
      # operator's runtime decision; apply preserves the current enabled state.
      url: mqtt.example.org
      port: 8883           # 1..65535
      transport: tls       # tcp | tls | wss
      auth_type: basic     # none | basic | jwt
      username: u
      password: p          # avoid in shared profiles
      jwt_aud: ...
      jwt_refresh: 3600    # seconds, >= 0
      jwt_owner: <64 hex>
      jwt_email: ...
      ca_cert: ...
      topic_prefix: meshcore
      iata_override: ...
      # jwt_token is NOT accepted — the device mints it at connect
```

Future sections (`radio`, `repeater`, `companion`, `display`) will appear
alongside `wifi`/`mqtt` as those device types gain profile support.

> **`region` (mqtt.iata) is per-operator-location.** Do NOT set it in a shared
> or org-wide catalog profile — it overrides the region of everyone who applies
> the profile. Brokers are usually org-wide and safe to share; region is not.
> Include `region` only in a profile meant for exactly one location.

Only keys you include are applied — the client writes field-at-a-time and leaves
everything else on the device untouched. Unknown keys, wrong types, out-of-range
values, and duplicate/out-of-range broker slots are **rejected**, not ignored.

**Do not put real secrets in a shared profile.** `password`, `jwt_token`, and
WiFi `password` are representable so a private profile *can* set them, but a
profile published to a catalog is public.

## Catalog manifest — `profiles.json`

```json
{
  "manifest_version": 1,
  "profiles": [
    {
      "name": "...",
      "description": "...",
      "region": "IAD",
      "schema_version": 1,
      "status": "published",
      "url": "https://absolute/url/to/profile.yaml"
    }
  ]
}
```

- `status`: `published` (shown in the app) or `retired` (kept for history, hidden).
- `url`: absolute. Relative URLs are not resolved.

## How the app resolves a source URL (tail-detection)

A user can point the app at any HTTP source. The tail of the URL decides how it's read:

| URL ends in | Treated as |
|---|---|
| `.json` | a catalog manifest (lists profiles to pick from) |
| `.yaml` / `.yml` | a single profile, applied directly |
| `/` (or no filename) | fetch `<url>profiles.json` by convention |

There is **no** reliance on HTTP directory listing — a directory URL resolves to
`<dir>/profiles.json`. Host `profiles.json` + your YAMLs on any HTTP server and
your catalog behaves exactly like this one.

## Radio presets: `radio-presets/`

The app's regional radio preset list (frequency, bandwidth, spreading factor, coding
rate) comes from two files. The app ships with a copy of both, so it works offline,
and refreshes them from here. **An edit here reaches users on their next refresh,
with no app release** (GitHub's raw-file cache can delay it by about five minutes).

| File | What it is | Who edits it |
|---|---|---|
| `meshcore-upstream.json` | MeshCore's suggested presets, maintained by Liam Cottle, mirrored unmodified from `https://api.meshcore.nz/api/v1/config` | Nobody by hand. A scheduled workflow rewrites it when the upstream list changes |
| `offband.json` | Offband's overlay: presets the upstream list lacks | People, by PR |

**Precedence:** the app shows both lists. When an overlay entry has the same `title`
as an upstream entry, the overlay entry wins. That must be deliberate, so the entry
must also set `"overrides_upstream": true`; the validator rejects an unmarked clash.

Check your change before opening a PR:

```
python scripts/validate_radio_presets.py
```

### Overlay file: `offband.json`

```json
{
  "format": "offband-radio-presets",
  "format_version": 1,
  "description": "...",
  "presets": [
    {
      "id": "usa-philly-mesh",
      "title": "USA - Philly Mesh",
      "region": "USA",
      "frequency": 919.5,
      "bandwidth": 500,
      "spreading_factor": 10,
      "coding_rate": 5,
      "tx_power": 20,
      "path_hash_size": 2,
      "status": "published",
      "notes": "Where the values come from, and when they were checked."
    }
  ]
}
```

| Field | Required | Rule |
|---|---|---|
| `id` | yes | Stable key: lowercase letters, digits, single hyphens. Never reuse or change it |
| `title` | yes | Shown in the picker; unique in this file |
| `region` | yes | Picker group, e.g. `USA`, `Russia`, `Off-Grid`. Use the same word the upstream titles start with, so both lists land in one group |
| `frequency` | yes | MHz, a JSON number, 150 to 2500 |
| `bandwidth` | yes | kHz, one of 7.8, 10.4, 15.6, 20.8, 31.25, 41.7, 62.5, 125, 250, 500 |
| `spreading_factor` | yes | 5 to 12 |
| `coding_rate` | yes | The denominator of 4/x: 5 to 8 (4/5 is `5`) |
| `tx_power` | no | dBm, whole number, -9 to 30. Omit to leave the radio's power alone |
| `path_hash_size` | no | **Bytes**, 1 to 3. The app converts to the firmware's zero-based mode (2 bytes = mode 1). Omit to leave the radio's setting alone |
| `off_grid` | no | `true` marks a client-repeat (off-grid) frequency |
| `overrides_upstream` | no | `true` when this entry deliberately replaces an upstream entry with the same title |
| `status` | yes | `published` (shown) or `retired` (kept for history, hidden) |
| `notes` | no | Source and date of the values. Not shown in the app |

Numbers must be JSON numbers, not strings. Unknown keys are rejected.

**To add** a preset, append an entry with a new `id`. **To change** one, edit its
values in place and update `notes`. **To retire** one, set `status` to `"retired"`;
don't delete it, and never reuse its `id`.

### Upstream mirror: `meshcore-upstream.json`

`suggested_radio_settings` is copied byte-for-byte from the API (whose numbers are
strings), wrapped with `format`, `format_version`, `source`, `credit` and
`updated_at` (when the upstream content last changed). The workflow validates the
fetched list before writing; if the API is unreachable or its shape changes, the run
fails and the last good mirror stays in place.
