# Maple World Frontend

Godot 4 client for the Maple World turn-based RPG backend (`../MapleWebBackEnd`).

## Current features

- Account sign-up, then character creation: pick a job (the class follows) and a name checked against the backend's rules.
- Sign in with JWT; the access token is refreshed automatically and logout blacklists the refresh token.
- Adventure board: character summary, stamina, normal dungeons, and resuming an active battle (`/api/battles/active/`).
- Turn-based battle against several enemies: click to target, attack, skills (single, area, self), battle items, forfeit, and a result screen with EXP, Lumis, level-up and drops. Actions carry `expected_version` and a `client_action_id`, so stale or retried actions are safe.
- Character profile with currency, progression, combat stats, equipment slots, and learned skills.
- Inventory with search and category filter. Double-click equips (into a free slot, or replacing the compared one), uses buff items, or opens Aurora enhancement for an essence. Hovering shows the item; equipment is compared with the equipped item of the same slot, and a middle click cycles through worn rings and pendants.
- Shop: buy from shop categories (Lumis or Nova), sell from the bag, and buy back any of the last 10 sales. Double-click buys, sells or buys back; stackable items and sales ask for a quantity.
- Settings: windowed or borderless fullscreen, window size, and BGM/SFX volume, saved to `user://settings.cfg`.
- Enhancement: Lumen Ascend with live rates, Aurora reveal, and Essence rerolls.
- Pixel-art icon set for the current backend item templates under `assets/items/icons/`.

## Run

1. Install Godot 4.7 or newer.
2. Import `project.godot` from this directory.
3. Press `F5`, sign in (or create an account), select a normal dungeon, and enter battle.

The client talks to the deployed backend at `https://maplewebbackend.onrender.com` by default.
The login screen pings it on open and shows whether it is online. A sleeping Render
instance can take up to a minute to wake up, so requests wait up to 60 seconds.

Run `battle_screen.tscn` directly with `F6` to use the offline mock battle.

## Backend URL

The API base URL comes from the project setting `maple_world/network/api_base_url`
(default `https://maplewebbackend.onrender.com/api`). To work against a local Django
backend, override it for one run with a user argument:

```bash
godot --path . -- --api-url=http://127.0.0.1:8000/api
```

In the editor, the same argument goes in Project Settings → Editor → Run → Main Run Args
(`-- --api-url=http://127.0.0.1:8000/api`).

A Web (HTML5) export runs in a browser, so the backend must list the page's origin in
`CORS_ALLOWED_ORIGINS`. Desktop builds are not affected by CORS.

## Project layout

- `src/app/scene_router.gd` — autoload `SceneRouter`: scene paths, navigation, redirect to login when the session expires.
- `src/network/api_client.gd` — autoload `ApiClient`: JSON requests, JWT refresh, list/error helpers. JSON numbers arrive as floats, so build URLs and lookup keys from IDs with `ApiClient.id_string()`.
- `src/session/session_store.gd` — autoload `SessionStore`: signed-in player state.
- `src/app/game_settings.gd` — autoload `GameSettings`: display and audio options. Audio buses `BGM` and `SFX` are in `default_bus_layout.tres`; play music on `BGM` and sound effects on `SFX` so the volume sliders apply.
- `src/shared/items/` — `ItemIcons` (template name → icon), `ItemTypes`, `ItemTooltip` (item description and stat comparison) and `ItemHoverTooltip` (the mouse-following tooltip).
- `tests/support/fake_http_server.gd` — `FakeHttpServer`, an in-process HTTP server for tests that need the API.
- `src/shared/ui/main_theme.tres` — project-wide theme. Use the `PrimaryButton`, `CompactPanel`, `HPBar`, `MPBar`, `EnemyHPBar` and `EXPBar` type variations instead of per-scene style overrides.
- `src/features/<feature>/` — one folder per screen, split into `data`, `domain` and `presentation` where needed.

## Tests

Each `tests/check_*.tscn` is a headless smoke test that exits non-zero on failure. Run them all with:

```bash
GODOT=/path/to/Godot_v4.7.2-stable_win64_console.exe tools/run_tests.sh
```

## Pixel art direction

- The project uses nearest-neighbor texture filtering and 2D pixel snapping.
- Target canvas: 1280×720, 16:9.
- Recommended authored character height: 128–256 pixels for a detailed side-scrolling look.
- Runtime item icons: 256×256 RGBA PNG.
- Keep gameplay sprites at integer scale values whenever possible.
