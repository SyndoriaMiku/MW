extends Node


func _ready() -> void:
	var packed: PackedScene = load("res://src/features/inventory/presentation/inventory_screen.tscn")
	if packed == null:
		printerr("INVENTORY_SCENE_LOAD_FAILED")
		get_tree().quit(1)
		return
	var screen: Control = packed.instantiate()
	var mock_template := {
		"id": "different-backend-id",
		"name": "Copper Hammer",
		"item_type": "weapon",
		"minimum_level": 1,
		"att_boost": 5,
	}
	var texture: Texture2D = screen._resolve_item_icon(mock_template)
	if texture == null:
		printerr("INVENTORY_ICON_RESOLVE_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	var card: Control = screen._create_item_card({
		"id": 1,
		"quantity": 1,
		"lumen_ascend_level": 4,
		"aurora_level": 1,
		"template": mock_template,
	})
	if card == null or card.get_child_count() == 0:
		printerr("INVENTORY_CARD_BUILD_FAILED")
		card.free()
		screen.free()
		get_tree().quit(1)
		return
	screen._equipped_slot_indices_by_type = {"ring": {0: true, 1: true}}
	if screen._next_available_slot_index("ring") != 2:
		printerr("INVENTORY_MULTI_SLOT_SELECTION_FAILED")
		card.free()
		screen.free()
		get_tree().quit(1)
		return
	screen._equipped_item_ids = {"1": true}
	screen._apply_equipment_response({"item": {"id": 1, "template": mock_template}}, "1", true)
	if screen._equipped_item_ids.has("1"):
		printerr("INVENTORY_UNEQUIP_SNAPSHOT_FAILED")
		card.free()
		screen.free()
		get_tree().quit(1)
		return
	screen._apply_equipment_response({"equipped": {"item": {"id": 1, "template": mock_template}}}, "1", false)
	if not screen._equipped_item_ids.has("1"):
		printerr("INVENTORY_EQUIP_SNAPSHOT_FAILED")
		card.free()
		screen.free()
		get_tree().quit(1)
		return
	print("INVENTORY_UI_OK texture=%s card=%s" % [texture.get_class(), card.get_class()])
	card.free()
	screen.free()
	get_tree().quit(0)
