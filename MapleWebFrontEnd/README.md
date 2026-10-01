# Maple World Frontend

Godot 4 client for the Maple World turn-based RPG backend (`../MapleWebBackEnd`).

## Current features

- Sign in with JWT; the access token is refreshed automatically and logout blacklists the refresh token.
- Adventure board: character summary, stamina, normal dungeons, and resuming an active battle (`/api/battles/active/`).
- Turn-based battle with attack, skills (cooldown and MP aware), and an event-driven combat log.
- Character profile with currency, progression, combat stats, equipment slots, and learned skills.
- Inventory with search, category filter, and equip/unequip.
- Enhancement: Lumen Ascend with live rates, Aurora reveal, and Essence rerolls.
- Pixel-art icon set for the current backend item templates under `assets/items/icons/`.

## Run locally

1. Install Godot 4.7 or newer.
2. Import `project.godot` from this directory.
3. Start the Django backend at `http://127.0.0.1:8000`.
4. Press `F5`, sign in, select a normal dungeon, and enter battle.

Run `battle_demo.tscn` directly with `F6` to use the offline mock battle.

## Backend URL

The API base URL comes from the project setting `maple_world/network/api_base_url`
(default `http://127.0.0.1:8000/api`). Override it for one run with a user argument:

```bash
godot --path . -- --api-url=http://127.0.0.1:8765/api
```

## Project layout

- `src/app/scene_router.gd` — autoload `SceneRouter`: scene paths, navigation, redirect to login when the session expires.
- `src/network/api_client.gd` — autoload `ApiClient`: JSON requests, JWT refresh, list/error helpers.
- `src/session/session_store.gd` — autoload `SessionStore`: signed-in player state.
- `src/shared/items/` — `ItemIcons` (template name → icon) and `ItemTypes`.
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
