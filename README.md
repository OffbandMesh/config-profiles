# Offband config profiles

Community-maintained device configuration profiles for [Offband
Meshcore](https://github.com/OffbandMesh/meshcore-client). A profile is a small
YAML file — region, WiFi, MQTT broker pool — that the app applies to a device
(observer / repeater / companion) instead of hand-entering each field.

This repo is the **reference catalog**. It is also a **template**: any region can
host its own catalog on any HTTP server and point users at it. Offband does not
gatekeep — see *Host your own* below.

## Using profiles (in the app)

1. **Curated catalog** — the app reads [`profiles.json`](profiles.json) from here
   by default and lists the `published` entries.
2. **Any source URL** — point the app at another region's catalog or a single
   profile. The URL's tail decides how it's read (`.json` = catalog, `.yaml` =
   one profile, trailing `/` = `…/profiles.json`). See [SCHEMA.md](SCHEMA.md).

The app **previews the exact changes and asks you to confirm before applying**,
whatever the source. That confirm step — not the source — is what keeps a bad
profile from mis-pointing your MQTT or region. Read the diff.

## Contributing a profile

1. Add a YAML under [`profiles/`](profiles/) — copy
   [`profiles/example.yaml`](profiles/example.yaml). Validate it against
   [SCHEMA.md](SCHEMA.md).
2. Add an entry to [`profiles.json`](profiles.json) (`status: "published"`),
   `url` pointing at the raw file.
3. Open a PR. **No secrets** — this repo is public; `password` / `jwt_token` /
   WiFi password do not belong in a shared profile.

**Retiring:** set the entry's `status` to `"retired"`. It stays for history and
disappears from the app's picker. Don't delete — retire.

## Host your own (federation)

Put `profiles.json` + your YAMLs on any static HTTP host (GitHub Pages,
raw.githubusercontent, S3, your own box). Give users the directory URL (or the
`profiles.json` URL) and the app treats it exactly like this catalog. Use
[`profiles.json.example`](profiles.json.example) as a starting point. A region
that would rather not depend on Offband can run entirely on its own catalog.

## License

MIT — see [LICENSE](LICENSE). Profiles you contribute are shared under the same.
