class_name ItemIcons
extends RefCounted

## Bundled icon for each backend item template. Keyed by the lower-cased template
## name because template IDs differ between local databases.

const ICON_PATHS := {
	"copper hammer": "res://assets/items/icons/copper_hammer.png",
	"copper essence": "res://assets/items/icons/copper_essence.png",
	"iron essence": "res://assets/items/icons/iron_essence.png",
	"gold essence": "res://assets/items/icons/gold_essence.png",
	"eternal essence": "res://assets/items/icons/eternal_essence.png",
	"copper bow": "res://assets/items/icons/copper_bow.png",
	"copper staff": "res://assets/items/icons/copper_staff.png",
}


static func for_template(template: Dictionary) -> Texture2D:
	var key := str(template.get("name", "")).strip_edges().to_lower()
	var path: String = ICON_PATHS.get(key, "")
	if path.is_empty():
		return null
	return load(path) as Texture2D
