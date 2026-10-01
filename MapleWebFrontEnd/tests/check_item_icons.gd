extends Node


func _ready() -> void:
	for icon_name in ItemIcons.ICON_PATHS:
		var path: String = ItemIcons.ICON_PATHS[icon_name]
		var texture := ItemIcons.for_template({"name": icon_name.capitalize()})
		print("ITEM_ICON name=%s type=%s path=%s" % [
			icon_name,
			texture.get_class() if texture != null else "null",
			path,
		])
		if texture == null:
			printerr("ITEM_ICON_MISSING %s" % path)
			get_tree().quit(1)
			return
	var profile_script: GDScript = load("res://src/features/character/presentation/character_profile.gd")
	var profile: Control = profile_script.new()
	# Icons resolve by template name, so a backend with different template IDs still works.
	profile._equipped_items = [{
		"slot": 9,
		"slot_index": 0,
		"item": {
			"lumen_ascend_level": 4,
			"lumen_breakdown": {
				"current_level": 4,
				"tier": {"id": 1, "name": "Copper Tier", "tier": 1, "max_level": 8},
				"levels": [],
				"total": {"hp_boost": 0, "mp_boost": 0, "att_boost": 8, "str_boost": 8, "agi_boost": 0, "int_boost": 0},
			},
			"aurora_level": 1,
			"aurora_lines": [{"line_index": 0, "stat_type": "att", "line_type": "percent", "value": 1.0}],
			"template": {
				"id": "different-backend-id", "name": "Copper Hammer", "item_type": "weapon", "minimum_level": 1, "att_boost": 5, "hp_boost": 10,
				"item_sets": [{
					"id": 1, "name": "Copper Set", "description": "Starter set",
					"items": [{"id": "different-backend-id", "name": "Copper Hammer", "item_type": "weapon"}],
					"effects": [{"id": 1, "required_count": 1, "att_boost": 3, "str_boost": 2}],
				}],
			},
		},
	}]
	var slot_view: Control = profile._create_slot_button(
		{"type": "weapon", "index": 0, "short": "WPN", "name": "Weapon"},
		Vector2(58, 58)
	)
	if slot_view.custom_minimum_size != Vector2(58, 58):
		printerr("EQUIPMENT_SLOT_SIZE_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	var rendered_texture := _find_texture_rect(slot_view)
	if rendered_texture == null or rendered_texture.texture == null:
		printerr("EQUIPMENT_TEXTURE_RENDER_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	var tooltip_stats: String = profile._equipment_stat_bbcode(
		profile._equipped_items[0].item.template,
		profile._equipped_items[0].item
	)
	if tooltip_stats.find("ATT:") < 0 or tooltip_stats.find("13") < 0 or tooltip_stats.find("5") < 0 or tooltip_stats.find("8") < 0 or tooltip_stats.find("base") >= 0 or tooltip_stats.find("lumen") >= 0:
		printerr("EQUIPMENT_TOOLTIP_STATS_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	var hp_line_start := tooltip_stats.find("HP:")
	var hp_line_end := tooltip_stats.find("\n", hp_line_start)
	var hp_line := tooltip_stats.substr(hp_line_start, hp_line_end - hp_line_start if hp_line_end >= 0 else -1)
	if hp_line.find("(") >= 0:
		printerr("BASE_ONLY_STAT_BREAKDOWN_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	var str_line_end := tooltip_stats.find("\n")
	var str_line := tooltip_stats.substr(0, str_line_end)
	if str_line.find("(") < 0 or str_line.find("]0[") < 0 or str_line.find("]8[") < 0:
		printerr("ZERO_BASE_LUMEN_BREAKDOWN_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	var mock_set: Dictionary = profile._equipped_items[0].item.template.item_sets[0]
	if profile._equipped_set_piece_count(mock_set) != 1 or profile._set_effect_stats_text(mock_set.effects[0]).find("ATT +3") < 0:
		printerr("EQUIPMENT_SET_EFFECT_MAPPING_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	profile._setup_item_tooltip()
	profile._build_item_tooltip(profile._equipped_items[0])
	if profile._tooltip_box == null or profile._tooltip_box.get_child_count() < 10:
		printerr("EQUIPMENT_TOOLTIP_BUILD_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	var lumen_title_found := false
	for tooltip_child in profile._tooltip_box.get_children():
		if tooltip_child is Label and tooltip_child.text == "Lumen Ascend 4/8":
			lumen_title_found = true
			break
	if not lumen_title_found:
		printerr("LUMEN_MAX_LEVEL_DISPLAY_FAILED")
		slot_view.free()
		profile.free()
		get_tree().quit(1)
		return
	print("EQUIPMENT_ICON_MAPPING_OK size=%s stats=%s" % [slot_view.custom_minimum_size, tooltip_stats.replace("\n", " | ")])
	slot_view.free()
	profile.free()
	get_tree().quit(0)


func _find_texture_rect(node: Node) -> TextureRect:
	if node is TextureRect:
		return node
	for child in node.get_children():
		var result := _find_texture_rect(child)
		if result != null:
			return result
	return null
