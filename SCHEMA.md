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
