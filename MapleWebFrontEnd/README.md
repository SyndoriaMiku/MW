# Maple World Frontend

Godot 4 client for the Maple World turn-based RPG backend.

## Current vertical slice

- One player versus one monster.
- Attack action and simple turn resolution.
- HP/MP HUD, combat log, victory state, and retry.
- Mock repository so the scene can run before a demo dungeon exists on the backend.
- HTTP client and repository boundary prepared for Django integration.
- Active battle detection and Resume Battle flow backed by `/api/battles/active/`.
- Character profile with account currency, progression, combat stats, and learned skills.
- Pixel-art icon set for all current backend item templates under `assets/items/icons/`.

## Run locally

1. Install Godot 4.3 or newer.
2. Import `project.godot` from this directory.
3. Start the Django backend at `http://127.0.0.1:8000`.
4. Press `F5`, sign in, select a normal dungeon, and enter battle.

Run `battle_demo.tscn` directly with `F6` to use the offline mock battle.

The initial scene intentionally uses only Godot controls and colors, so no external assets are required.

## Backend switch

The normal `F5` flow uses the Django backend. Running the battle scene directly uses mock mode, which keeps UI work unblocked when the backend is offline.

## Pixel art direction

- The project uses nearest-neighbor texture filtering and 2D pixel snapping.
- Target canvas: 1280×720, 16:9.
- Recommended authored character height: 128–256 pixels for a detailed side-scrolling look.
- Runtime item icons: 256×256 RGBA PNG.
- Keep gameplay sprites at integer scale values whenever possible.
