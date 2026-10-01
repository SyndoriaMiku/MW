# Item icon set

AI-generated high-resolution pixel-art source icons for the current backend `ItemTemplate` rows.

## Art direction

- Square 256×256 RGBA PNG runtime files with transparent backgrounds.
- Detailed 32-bit-era pixel-art rendering for a high-resolution 2D side-scrolling RPG.
- Upper-left cool highlight, compact internal shadows, crisp silhouettes.
- Copper weapons share dark wood, leather wrapping, hammered copper, and teal oxidation.
- Essence tiers are standalone glowing gemstones and progress through copper, iron, gold, and eternal prismatic materials.
- No baked icon frames, labels, logos, or background glow.

Register each icon in `ItemIcons.ICON_PATHS` (`src/shared/items/item_icons.gd`), keyed by the lower-cased backend template name; template IDs differ between local databases. Keep textures on nearest-neighbor filtering and prefer integer display scales.

`source/` holds high-resolution originals. It has a `.gdignore`, so Godot neither imports nor exports it.
