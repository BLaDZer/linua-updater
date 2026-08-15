# Task 08 — Configurable / non-stale endpoints & mirrors

## How it works now

- All network endpoints are hardcoded:
  - `VERSION_CHECK_URL` → `raw.githubusercontent.com/l1ntol/linua-updater/main/version.json` (`:47`).
  - Region detection → `https://ipapi.co/json/` (`NetworkDiagnostics.detect_region`, `:562`).
  - Proxy probe list → 6 hardcoded local ports (`:602`).
  - Mirror fallback table → `{"github.com": "mirror.ghproxy.com/https://github.com", "raw.githubusercontent.com": "raw.fastgit.org"}` (`:675`).
- `raw.fastgit.org` is long dead and `mirror.ghproxy.com` is unreliable/defunct; the fallback silently wastes retry time when triggered.
- All 109 DLC download URLs point to one Cloudflare Workers host (`penis.nicole-popova66.workers.dev`) baked into `DLCDatabase`; there is no user/operator-editable way to supply a different CDN or mirror.
- No user-editable configuration of any of these (the doc notes this in §10).

## How it should work

- Endpoints, proxy ports, and mirror table live in config (`ConfigManager`/`config.json`) with current values as defaults, so an operator can override them without rebuilding the binary.
- For the heavy one — the DLC CDN — a configurable base URL (or per-entry `url` overrides) lets the catalog be distributed separately from the app or pointed at a mirror.
- The mirror list is kept functional: dead entries removed, working mirrors (or a sensible default) used, and individually gated so a dead mirror doesn't add latency.
- `version.json`/`update_cache.json` (`UpdateChecker`, `:198`) already provide a mechanism to ship new URLs to clients — document that as the distribution path for catalog changes.

## What needs fixing

1. `ConfigManager` — add optional keys: `download_mirrors`, `proxy_ports`, `region_api`, `version_check_url` (defaulting to the current constants).
2. `SmartDownloader.download` (`:675`) — read mirror table from settings; drop `raw.fastgit.org`; make each mirror attempt optional/skippable.
3. `NetworkDiagnostics` (`:602`) — source the proxy probe list from settings.
4. `DLCDatabase` — decide: keep 109 URLs but make the host overridable via config base URL, or document that catalog updates ship via app updates (version.json). Avoid a runtime catalog download unless desired — simplest scope: configurable base host.
5. Update `docs/architecture.md` §5 / §10 (remove or amend the "no user-editable mirror configuration" note as applicable).