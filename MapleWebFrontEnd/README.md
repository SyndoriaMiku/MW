# Maple World Frontend

Godot 4 client for the Maple World turn-based RPG backend (`../MapleWebBackEnd`).

## Current features

- Account sign-up, then character creation: pick a job (the class follows) and a name checked against the backend's rules.
- Sign in with JWT; the access token is refreshed automatically and logout blacklists the refresh token.
- Hub (main menu, Material 3 Expressive, light theme from the seed color `#336DFF`): a header with the character, Lumis/Nova and a live stamina bar (with time to the next point and to full), a content box, and a navigation bar for Home, Adventure, Character, Inventory, Enhance, Shop and Settings. Pages keep their state and reload when shown again; Escape or the mouse back button returns to the previous page. Data comes from `session/bootstrap/` in one request.
- Home: key art (drawn until `assets/ui/home_background.png` exists), the running rate events, and Adventure / Resume battle.
- Adventure: the world map — region chips, then the dungeons of each location, in the order set in Studio (`order`); dungeons without a location are under "Elsewhere". Normal dungeons cost stamina; boss dungeons show their reset (daily/weekly/monthly) and party size, are started by the party leader, and create a party of one first when the player has none. Enter is disabled with the reason (level, stamina, leader, party size, battle in progress); server refusals (e.g. already cleared this week) are shown.
- Quests: daily, weekly and story quests with each objective's progress and the rewards; completed quests are claimed there. A badge on Quests and a card on Home count the quests ready to claim.
- Skills: learned skills (damage now and at the next level, MP, cooldown, target) and the skills still to unlock with their level. Upgrades that need materials list them with the amount held and are bought there; the others say they happen on level-up.
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
3. Press `F5`, sign in (or create an account), open Adventure in the hub, and enter a dungeon.

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

- `src/app/scene_router.gd` — autoload `SceneRouter`: scene paths, navigation, redirect to login when the session expires. Character, Inventory, Enhancement and Shop are hub pages: `go_to()` one of them switches the hub's page (or opens the hub on it).
- `src/features/hub/` — `HubScreen`, its pages (`HomePage`, `AdventurePage`), `NavBar` (with badges), `HubWidgets` (header, list cards, chips, detail card shared by the hub's own pages), `StaminaBar` and `StaminaClock` (client-side stamina regeneration). `src/features/quests/` (`QuestsPage`, `QuestRules`) and `src/features/skills/` (`SkillsPage`, `SkillRules`) are hub pages too. Screens embedded as pages hide their back button through `HubEmbed` and may implement `reload_page()` and `apply_args(args)`.
- `src/network/api_client.gd` — autoload `ApiClient`: JSON requests, JWT refresh, list/error helpers. JSON numbers arrive as floats, so build URLs and lookup keys from IDs with `ApiClient.id_string()`.
- `src/network/game_cache.gd` — autoload `GameCache`: read-through cache for GETs. Reference data (classes, jobs, slots, dungeons, shop categories, skills) lives 6 hours (the dungeon list 30 minutes, since Studio reorders it), and on disk (`user://cache/`) for the deployed server; player data (character, profile, inventory, equipment, buy back, shop stock, active battle, Lumen preview) lives 5 minutes and is dropped by any POST that may change it (`INVALIDATES`). Concurrent identical requests share one call. Screens read through `GameCache.get_json()` / `get_all()`; Refresh buttons call `GameCache.clear_all()`. Battle state is never cached.
- `src/session/session_store.gd` — autoload `SessionStore`: signed-in player state.
- `src/app/game_settings.gd` — autoload `GameSettings`: display and audio options. Audio buses `BGM` and `SFX` are in `default_bus_layout.tres`; play music on `BGM` and sound effects on `SFX` so the volume sliders apply.
- `src/shared/items/` — `ItemIcons` (template name → icon), `ItemTypes`, `ItemTooltip` (item description and stat comparison) and `ItemHoverTooltip` (the mouse-following tooltip).
- `tests/support/fake_http_server.gd` — `FakeHttpServer`, an in-process HTTP server for tests that need the API.
- `src/shared/ui/m3.gd` — `M3`: the Material 3 color roles (light scheme from the seed `#336DFF`: primary is the seed, the other roles are the M3 tonal palettes of its hue), extended game colors, type scale, corner radii, motion and Material Symbols helpers. Reference colors through these roles; never hard-code them.
- `src/shared/ui/main_theme.tres` — project-wide theme, **generated** from `M3` by `tools/build_theme.gd` (do not edit by hand; change `m3.gd` and run `godot --headless --path . --script tools/build_theme.gd`). Type variations: buttons `PrimaryButton`, `OutlinedButton`, `TextButton`, `DangerButton`, `ChipButton`, `ListItemButton`; panels `CompactPanel`, `TonalPanel`, `OutlinedPanel`, `DialogPanel`, `AvatarPanel`, `IconPanel`; labels `MutedLabel`, `AccentLabel`, `ErrorLabel`, `SuccessLabel`, `GoldLabel`, `EpicLabel`, `TitleLabel`, `HeadlineLabel`; bars `HPBar`, `MPBar`, `EnemyHPBar`, `EXPBar`.
- `src/shared/ui/ui_feedback.gd` — autoload `UiFeedback`: ripple and press-scale on every button; call `UiFeedback.attach(control)` for custom tappable cards.
- `assets/fonts/` — Roboto (text) and Material Symbols Rounded (icons); see its README for licenses.
- `src/features/<feature>/` — one folder per screen, split into `data`, `domain` and `presentation` where needed.

## Tests

Each `tests/check_*.tscn` is a headless smoke test that exits non-zero on failure. Run them all with:

```bash
GODOT=/path/to/Godot_v4.7.2-stable_win64_console.exe tools/run_tests.sh
```

## Pixel art direction

- The project uses nearest-neighbor texture filtering and snaps 2D transforms to pixels. Vertex snapping is off so rounded UI shapes stay smooth.
- Target canvas: 1280×720, 16:9.
- Recommended authored character height: 128–256 pixels for a detailed side-scrolling look.
- Runtime item icons: 256×256 RGBA PNG.
- Keep gameplay sprites at integer scale values whenever possible.
