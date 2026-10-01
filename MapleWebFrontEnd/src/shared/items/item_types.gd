class_name ItemTypes
extends RefCounted

## Backend `ItemTemplate.item_type` values that can be equipped.
const EQUIPMENT := {
	"pendant": true, "earring": true, "ring": true, "belt": true,
	"face": true, "eye": true, "hat": true, "top": true,
	"bottom": true, "shoes": true, "cape": true, "gloves": true,
	"shoulder": true, "weapon": true,
}


static func is_equipment(item_type: String) -> bool:
	return EQUIPMENT.has(item_type)
