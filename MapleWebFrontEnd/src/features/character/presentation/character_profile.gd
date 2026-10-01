extends Control

@onready var back_button: Button = %BackButton
@onready var refresh_button: Button = %RefreshButton
@onready var character_name: Label = %CharacterName
@onready var account_name: Label = %AccountName
@onready var class_job_label: Label = %ClassJobLabel
@onready var level_label: Label = %LevelLabel
@onready var exp_label: Label = %ExpLabel
@onready var exp_progress: ProgressBar = %ExpProgress
@onready var currency_label: Label = %CurrencyLabel
@onready var stamina_label: Label = %StaminaLabel
@onready var hp_value: Label = %HPValue
@onready var mp_value: Label = %MPValue
@onready var attack_value: Label = %AttackValue
@onready var damage_value: Label = %DamageValue
@onready var strength_value: Label = %StrengthValue
@onready var agility_value: Label = %AgilityValue
@onready var intelligence_value: Label = %IntelligenceValue
@onready var drop_rate_value: Label = %DropRateValue
@onready var final_damage_value: Label = %FinalDamageValue
@onready var base_stats_label: Label = %BaseStatsLabel
@onready var accessory_grid: GridContainer = %AccessoryGrid
@onready var armor_grid: GridContainer = %ArmorGrid
@onready var weapon_slot_host: CenterContainer = %WeaponSlotHost
@onready var skill_list: ItemList = %SkillList
@onready var skill_name: Label = %SkillName
@onready var skill_details: Label = %SkillDetails
@onready var skill_description: Label = %SkillDescription
@onready var status_label: Label = %StatusLabel

var _character: Dictionary = {}
var _profile: Dictionary = {}
var _classes: Array = []
var _jobs: Array = []
var _skills: Array = []
var _equipped_items: Array = []
var _item_tooltip: PopupPanel
var _tooltip_box: VBoxContainer

const ACCESSORY_SLOTS := [
	{"type": "pendant", "index": 0, "short": "P1", "name": "Pendant I"},
	{"type": "pendant", "index": 1, "short": "P2", "name": "Pendant II"},
	{"type": "earring", "index": 0, "short": "ER", "name": "Earring"},
	{"type": "belt", "index": 0, "short": "BT", "name": "Belt"},
	{"type": "face", "index": 0, "short": "FA", "name": "Face Accessory"},
	{"type": "eye", "index": 0, "short": "EY", "name": "Eye Accessory"},
	{"type": "ring", "index": 0, "short": "R1", "name": "Ring I"},
	{"type": "ring", "index": 1, "short": "R2", "name": "Ring II"},
	{"type": "ring", "index": 2, "short": "R3", "name": "Ring III"},
	{"type": "ring", "index": 3, "short": "R4", "name": "Ring IV"},
]

const ARMOR_SLOTS := [
	{"type": "hat", "index": 0, "short": "HT", "name": "Hat"},
	{"type": "top", "index": 0, "short": "TP", "name": "Top"},
	{"type": "bottom", "index": 0, "short": "BT", "name": "Bottom"},
	{"type": "shoes", "index": 0, "short": "SH", "name": "Shoes"},
	{"type": "gloves", "index": 0, "short": "GL", "name": "Gloves"},
	{"type": "shoulder", "index": 0, "short": "SD", "name": "Shoulder Armor"},
	{"type": "cape", "index": 0, "short": "CP", "name": "Cape"},
]

const SLOT_ID_TO_TYPE := {
	9: "weapon",
	10: "earring",
	11: "ring",
	12: "belt",
	13: "face",
	14: "eye",
	15: "hat",
	16: "top",
	17: "bottom",
	18: "shoes",
	19: "cape",
	20: "gloves",
	21: "shoulder",
	22: "pendant",
}


func _ready() -> void:
	_setup_item_tooltip()
	back_button.pressed.connect(_on_back_pressed)
	refresh_button.pressed.connect(_load_profile)
	skill_list.item_selected.connect(_on_skill_selected)
	if not SceneRouter.require_session():
		return
	await _load_profile()


func _load_profile() -> void:
	_set_loading(true, "Loading character profile...")
	var profile_response: Dictionary = await ApiClient.get_json("users/profile/")
	if not _accept_response(profile_response):
		return
	_profile = profile_response.get("data", {})

	var character_response: Dictionary = await ApiClient.get_json("characters/my/")
	if not _accept_response(character_response):
		return
	_character = character_response.get("data", {})
	SessionStore.character = _character

	var classes_response: Dictionary = await ApiClient.get_json("classes/")
	if not _accept_response(classes_response):
		return
	_classes = ApiClient.unwrap_list(classes_response.get("data", []))

	var jobs_response: Dictionary = await ApiClient.get_json("classes/jobs/")
	if not _accept_response(jobs_response):
		return
	_jobs = ApiClient.unwrap_list(jobs_response.get("data", []))

	var equipment_response: Dictionary = await ApiClient.get_json("inventory/equipped/")
	if not _accept_response(equipment_response):
		return
	_equipped_items = ApiClient.unwrap_list(equipment_response.get("data", []))

	_skills = _character.get("skills", [])
	_render_profile()
	_set_loading(false, "Character data synchronized with the server.")


func _render_profile() -> void:
	character_name.text = str(_character.get("name", "Unknown Adventurer"))
	account_name.text = "ACCOUNT  %s" % str(_profile.get("username", SessionStore.username))
	var class_name_text := _lookup_name(_classes, _character.get("character_class"))
	var job_name_text := _lookup_name(_jobs, _character.get("job"))
	class_job_label.text = "%s  •  %s" % [class_name_text, job_name_text]
	level_label.text = "LEVEL %d" % int(_character.get("level", 1))
	_render_exp()
	currency_label.text = "LUMIS  %d     NOVA  %d" % [
		int(_profile.get("lumis", 0)),
		int(_profile.get("nova", 0)),
	]
	stamina_label.text = "%d / %d" % [
		int(_character.get("current_stamina", 0)),
		int(_character.get("max_stamina", 0)),
	]
	hp_value.text = str(_character.get("total_hp", 0))
	mp_value.text = str(_character.get("total_mp", 0))
	attack_value.text = str(_character.get("total_att", 0))
	damage_value.text = str(_character.get("total_damage", 0))
	strength_value.text = str(_character.get("total_str", 0))
	agility_value.text = str(_character.get("total_agi", 0))
	intelligence_value.text = str(_character.get("total_int", 0))
	drop_rate_value.text = "%.0f%%" % (float(_character.get("drop_rate", 1.0)) * 100.0)
	final_damage_value.text = "+%.0f%%" % (float(_character.get("total_final_damage", 0.0)) * 100.0)
	base_stats_label.text = "BASE  HP %d  •  MP %d  •  ATT %d  •  STR %d  •  AGI %d  •  INT %d" % [
		int(_character.get("base_hp", 0)),
		int(_character.get("base_mp", 0)),
		int(_character.get("base_att", 0)),
		int(_character.get("base_str", 0)),
		int(_character.get("base_agi", 0)),
		int(_character.get("base_int", 0)),
	]
	_render_equipment()
	_render_skills()


func _render_exp() -> void:
	var current_exp := int(_character.get("current_exp", 0))
	var required_exp := int(_character.get("required_exp", 0))
	if required_exp <= 0:
		exp_progress.max_value = 1
		exp_progress.value = 0
		exp_label.text = "EXP  %d / —" % current_exp
		exp_progress.tooltip_text = "Backend must expose required_exp for the current level."
		return
	exp_progress.max_value = required_exp
	exp_progress.value = mini(current_exp, required_exp)
	exp_label.text = "EXP  %d / %d" % [current_exp, required_exp]
	exp_progress.tooltip_text = "%.1f%% to the next level" % (float(current_exp) / float(required_exp) * 100.0)


func _render_equipment() -> void:
	_clear_children(accessory_grid)
	_clear_children(armor_grid)
	_clear_children(weapon_slot_host)
	for slot in ACCESSORY_SLOTS:
		accessory_grid.add_child(_create_slot_button(slot, Vector2(58, 58)))
	for slot in ARMOR_SLOTS:
		armor_grid.add_child(_create_slot_button(slot, Vector2(58, 58)))
	var weapon_slot := {"type": "weapon", "index": 0, "short": "WPN", "name": "Weapon"}
	weapon_slot_host.add_child(_create_slot_button(weapon_slot, Vector2(58, 58)))


func _create_slot_button(slot: Dictionary, size: Vector2) -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = size
	panel.tooltip_text = "%s — Empty" % slot.name
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	var style := StyleBoxFlat.new()
	style.bg_color = Color("111a29")
	style.border_color = Color("34465e")
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.set_content_margin_all(4)
	panel.add_theme_stylebox_override("panel", style)

	var center := CenterContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(center)
	var empty_label := Label.new()
	empty_label.text = str(slot.short)
	empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	empty_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	empty_label.add_theme_color_override("font_color", Color("607089"))
	empty_label.add_theme_font_size_override("font_size", 11)
	empty_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(empty_label)

	var equipped := _find_equipped_item(str(slot.type), int(slot.index))
	if equipped.is_empty():
		return panel

	var item: Dictionary = equipped.get("item", {})
	var template: Dictionary = item.get("template", {})
	var icon_texture := ItemIcons.for_template(template)
	if icon_texture != null:
		empty_label.visible = false
		var texture_rect := TextureRect.new()
		texture_rect.custom_minimum_size = size - Vector2(10, 10)
		texture_rect.texture = icon_texture
		texture_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		texture_rect.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		texture_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		center.add_child(texture_rect)
		style.border_color = Color("53d985")
		style.set_border_width_all(2)
	panel.tooltip_text = ""
	panel.mouse_entered.connect(_show_item_tooltip.bind(equipped, panel))
	panel.mouse_exited.connect(_hide_item_tooltip)
	return panel


func _setup_item_tooltip() -> void:
	_item_tooltip = PopupPanel.new()
	_item_tooltip.name = "EquipmentTooltip"
	_item_tooltip.unresizable = true
	var style := StyleBoxFlat.new()
	style.bg_color = Color("26313d")
	style.border_color = Color("536272")
	style.set_border_width_all(2)
	style.set_corner_radius_all(7)
	_item_tooltip.add_theme_stylebox_override("panel", style)
	add_child(_item_tooltip)

	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 16)
	margin.add_theme_constant_override("margin_top", 14)
	margin.add_theme_constant_override("margin_right", 16)
	margin.add_theme_constant_override("margin_bottom", 14)
	_item_tooltip.add_child(margin)
	_tooltip_box = VBoxContainer.new()
	_tooltip_box.add_theme_constant_override("separation", 7)
	margin.add_child(_tooltip_box)


func _show_item_tooltip(equipped: Dictionary, _slot_control: Control) -> void:
	_build_item_tooltip(equipped)
	var viewport_size := get_viewport_rect().size
	var popup_size := Vector2i(410, mini(620, int(viewport_size.y) - 20))
	var mouse_position := get_viewport().get_mouse_position()
	var popup_position := Vector2i(mouse_position + Vector2(18, 12))
	if popup_position.x + popup_size.x > int(viewport_size.x) - 10:
		popup_position.x = maxi(10, int(mouse_position.x) - popup_size.x - 18)
	if popup_position.y + popup_size.y > int(viewport_size.y) - 10:
		popup_position.y = maxi(10, int(viewport_size.y) - popup_size.y - 10)
	_item_tooltip.popup(Rect2i(popup_position, popup_size))


func _hide_item_tooltip() -> void:
	if _item_tooltip != null:
		_item_tooltip.hide()


func _build_item_tooltip(equipped: Dictionary) -> void:
	for child in _tooltip_box.get_children():
		child.free()
	var item: Dictionary = equipped.get("item", {})
	var template: Dictionary = item.get("template", {})
	var item_name := str(template.get("name", "Unknown Item"))
	var item_type := str(template.get("item_type", "equipment")).replace("_", " ").capitalize()

	_add_lumen_summary(item)
	var name_label := _tooltip_label(item_name, 20, Color("f5f7fb"), HORIZONTAL_ALIGNMENT_CENTER)
	_tooltip_box.add_child(name_label)
	var trade_text := "Untradeable" if bool(item.get("is_untrade", false)) or not bool(template.get("is_tradeable", true)) else "Tradeable"
	_tooltip_box.add_child(_tooltip_label(trade_text, 13, Color("e49a55"), HORIZONTAL_ALIGNMENT_CENTER))
	_tooltip_box.add_child(HSeparator.new())

	var overview := HBoxContainer.new()
	overview.add_theme_constant_override("separation", 14)
	_tooltip_box.add_child(overview)
	var icon_panel := PanelContainer.new()
	icon_panel.custom_minimum_size = Vector2(104, 104)
	var icon_style := StyleBoxFlat.new()
	icon_style.bg_color = Color("56616d")
	icon_style.border_color = Color("8a96a2")
	icon_style.set_border_width_all(2)
	icon_style.set_corner_radius_all(5)
	icon_style.set_content_margin_all(7)
	icon_panel.add_theme_stylebox_override("panel", icon_style)
	overview.add_child(icon_panel)
	var icon := TextureRect.new()
	icon.texture = ItemIcons.for_template(template)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	icon_panel.add_child(icon)

	var summary := VBoxContainer.new()
	summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	summary.alignment = BoxContainer.ALIGNMENT_CENTER
	summary.add_child(_tooltip_label("CURRENTLY EQUIPPED", 17, Color("d7dee7"), HORIZONTAL_ALIGNMENT_RIGHT))
	summary.add_child(_tooltip_label(item_type, 14, Color("aebbc9"), HORIZONTAL_ALIGNMENT_RIGHT))
	summary.add_child(_tooltip_label("Required Level  %d" % int(template.get("minimum_level", 1)), 14, Color("eef2f6"), HORIZONTAL_ALIGNMENT_RIGHT))
	overview.add_child(summary)

	_add_set_effect_section(template, item)
	_tooltip_box.add_child(HSeparator.new())
	_tooltip_box.add_child(_tooltip_label("STAT BOOSTS", 13, Color("b8c2cc")))
	var stats := RichTextLabel.new()
	stats.bbcode_enabled = true
	stats.fit_content = true
	stats.scroll_active = false
	stats.custom_minimum_size = Vector2(0, 72)
	stats.text = _equipment_stat_bbcode(template, item)
	_tooltip_box.add_child(stats)

	_tooltip_box.add_child(HSeparator.new())
	_add_aurora_section(item)
	_tooltip_box.add_child(HSeparator.new())
	_tooltip_box.add_child(_tooltip_label("ADDITIONAL ENHANCEMENTS", 12, Color("8e9aa7")))
	_tooltip_box.add_child(_tooltip_label("Reserved for future equipment systems", 12, Color("697681")))


func _add_set_effect_section(template: Dictionary, item: Dictionary) -> void:
	var sets: Variant = item.get("set_effects", template.get("item_sets", []))
	if not sets is Array:
		return
	var visible_sets: Array = []
	for set_data in sets:
		if set_data is Dictionary:
			visible_sets.append(set_data)
	if visible_sets.is_empty():
		return
	_tooltip_box.add_child(HSeparator.new())
	_tooltip_box.add_child(_tooltip_label("SET EFFECT", 12, Color("9ca8b4")))
	for set_data in visible_sets:
		var set_name := str(set_data.get("name", "Equipment Set"))
		var active_count := _equipped_set_piece_count(set_data)
		var member_count := _set_member_count(set_data)
		var count_text := "  %d/%d" % [active_count, member_count] if member_count > 0 else ""
		_tooltip_box.add_child(_tooltip_label(set_name + count_text, 13, Color("e0c66d")))
		var effects: Variant = set_data.get("effects", [])
		if not effects is Array:
			continue
		for effect_value in effects:
			if not effect_value is Dictionary:
				continue
			var effect: Dictionary = effect_value
			var required_count := int(effect.get("required_count", 0))
			var is_active := active_count >= required_count
			var prefix := "●" if is_active else "○"
			var effect_text := "%s  %d SET  %s" % [prefix, required_count, _set_effect_stats_text(effect)]
			_tooltip_box.add_child(_tooltip_label(
				effect_text,
				12,
				Color("79dfa3") if is_active else Color("7d8995")
			))


func _equipped_set_piece_count(set_data: Dictionary) -> int:
	var member_ids := {}
	var members: Variant = set_data.get("items", [])
	if members is Array:
		for member_value in members:
			if member_value is Dictionary:
				member_ids[ApiClient.id_string(member_value.get("id"))] = true
	var equipped_member_ids := {}
	for equipped in _equipped_items:
		var equipped_item: Dictionary = equipped.get("item", {})
		var equipped_template: Dictionary = equipped_item.get("template", {})
		var template_id := ApiClient.id_string(equipped_template.get("id"))
		if member_ids.has(template_id):
			equipped_member_ids[template_id] = true
	return equipped_member_ids.size()


func _set_member_count(set_data: Dictionary) -> int:
	var members: Variant = set_data.get("items", [])
	return members.size() if members is Array else 0


func _set_effect_stats_text(effect: Dictionary) -> String:
	var parts := PackedStringArray()
	var definitions := [
		["hp_boost", "HP"], ["mp_boost", "MP"], ["att_boost", "ATT"],
		["str_boost", "STR"], ["agi_boost", "AGI"], ["int_boost", "INT"],
		["all_stats_boost", "ALL STATS"],
	]
	for definition in definitions:
		var value := float(effect.get(definition[0], 0))
		if not is_zero_approx(value):
			parts.append("%s %s" % [definition[1], _signed_number(value)])
	return "  •  ".join(parts) if not parts.is_empty() else "No stat bonus"


func _equipment_stat_bbcode(template: Dictionary, item: Dictionary) -> String:
	var output := PackedStringArray()
	var breakdown: Dictionary = item.get("stat_breakdown", {})
	var lumen_stats := _normalized_lumen_stats(item)
	var future_stats: Dictionary = item.get("enhancement_stat_boosts", {})
	var aurora_flat := _aurora_flat_stats(item)
	var stat_definitions := [
		["str", "STR"], ["agi", "AGI"], ["int", "INT"],
		["att", "ATT"], ["hp", "HP"], ["mp", "MP"],
		["all_stats", "ALL STATS"],
	]
	for definition in stat_definitions:
		var stat_key: String = definition[0]
		var stat_name: String = definition[1]
		var base_value := float(template.get("%s_boost" % stat_key, 0))
		var stat_breakdown: Dictionary = breakdown.get(stat_key, {})
		if stat_breakdown.has("base"):
			base_value = float(stat_breakdown.get("base", base_value))
		var lumen_value := float(stat_breakdown.get("lumen", lumen_stats.get(stat_key, 0)))
		var aurora_value := float(stat_breakdown.get("aurora", aurora_flat.get(stat_key, 0)))
		var future_value := float(stat_breakdown.get("other", future_stats.get(stat_key, 0)))
		var total := float(stat_breakdown.get("total", base_value + lumen_value + aurora_value + future_value))
		if is_zero_approx(total) and is_zero_approx(base_value) and is_zero_approx(lumen_value) and is_zero_approx(aurora_value) and is_zero_approx(future_value):
			continue
		var components := PackedStringArray()
		var has_non_base_component := not is_zero_approx(lumen_value) or not is_zero_approx(aurora_value) or not is_zero_approx(future_value)
		if has_non_base_component:
			components.append("[color=#ffffff]%s[/color]" % _plain_number(base_value))
		if not is_zero_approx(lumen_value):
			components.append("[color=#63d7ef]%s[/color]" % _plain_number(lumen_value))
		if not is_zero_approx(aurora_value):
			components.append("[color=#c48cff]%s[/color]" % _plain_number(aurora_value))
		if not is_zero_approx(future_value):
			components.append("[color=#73dda1]%s[/color]" % _plain_number(future_value))
		var stat_text := "[color=#edf2f7]%s:[/color]  [color=#59c9f5]%s[/color]" % [stat_name, _plain_number(total)]
		if has_non_base_component:
			stat_text += "  (%s)" % " + ".join(components)
		output.append(stat_text)
	var drop_rate := float(template.get("drop_rate_boost", 0.0))
	if not is_zero_approx(drop_rate):
		output.append("[color=#edf2f7]DROP RATE:[/color]  [color=#59c9f5]%s%%[/color]  ([color=#ffffff]%s%%[/color])" % [_plain_number(drop_rate), _plain_number(drop_rate)])
	if output.is_empty():
		return "[color=#8e9aa7]No direct stat boosts[/color]"
	return "\n".join(output)


func _normalized_lumen_stats(item: Dictionary) -> Dictionary:
	var result := {}
	var lumen_breakdown: Variant = item.get("lumen_breakdown", {})
	if not lumen_breakdown is Dictionary:
		return result
	var total: Variant = lumen_breakdown.get("total", {})
	if not total is Dictionary:
		return result
	for stat_key in ["hp", "mp", "att", "str", "agi", "int"]:
		result[stat_key] = float(total.get("%s_boost" % stat_key, 0))
	return result


func _add_lumen_summary(item: Dictionary) -> void:
	var lumen_level := int(item.get("lumen_ascend_level", 0))
	if lumen_level <= 0:
		return
	var max_level := 0
	var lumen_breakdown: Variant = item.get("lumen_breakdown", {})
	if lumen_breakdown is Dictionary:
		var tier: Variant = lumen_breakdown.get("tier")
		if tier is Dictionary:
			max_level = int(tier.get("max_level", 0))
	var level_text := "%d/%d" % [lumen_level, max_level] if max_level > 0 else str(lumen_level)
	_tooltip_box.add_child(_tooltip_label(
		"Lumen Ascend %s" % level_text,
		14,
		Color("63d7ef"),
		HORIZONTAL_ALIGNMENT_CENTER
	))


func _aurora_flat_stats(item: Dictionary) -> Dictionary:
	var result := {}
	for line_value in item.get("aurora_lines", []):
		if not line_value is Dictionary:
			continue
		var line: Dictionary = line_value
		if str(line.get("line_type", "flat")) != "flat":
			continue
		var stat_key := str(line.get("stat_type", ""))
		result[stat_key] = float(result.get(stat_key, 0)) + float(line.get("value", 0))
	return result


func _add_aurora_section(item: Dictionary) -> void:
	var aurora_level := int(item.get("aurora_level", 0))
	_tooltip_box.add_child(_tooltip_label("AURORA  +%d" % aurora_level, 14, Color("c48cff")))
	var lines: Variant = item.get("aurora_lines", [])
	if not lines is Array or lines.is_empty():
		_tooltip_box.add_child(_tooltip_label("No Aurora lines", 12, Color("8e9aa7")))
		return
	for line_value in lines:
		if not line_value is Dictionary:
			continue
		var line: Dictionary = line_value
		var suffix := "%" if str(line.get("line_type", "flat")) == "percent" else ""
		var text := "◆  %s  +%s%s" % [
			str(line.get("stat_type", "")).replace("_", " ").to_upper(),
			str(line.get("value", 0)),
			suffix,
		]
		_tooltip_box.add_child(_tooltip_label(text, 13, Color("d9a7ff")))


func _tooltip_label(text: String, font_size: int, color: Color, alignment := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var label := Label.new()
	label.text = text
	label.horizontal_alignment = alignment
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


func _signed_number(value: float) -> String:
	if is_equal_approx(value, round(value)):
		return "%+d" % int(value)
	return "%+.1f" % value


func _plain_number(value: float) -> String:
	if is_equal_approx(value, round(value)):
		return "%d" % int(value)
	return "%.1f" % value


func _find_equipped_item(item_type: String, slot_index: int) -> Dictionary:
	for equipped in _equipped_items:
		var item: Dictionary = equipped.get("item", {})
		var template: Dictionary = item.get("template", {})
		var resolved_type := str(template.get("item_type", ""))
		if resolved_type.is_empty():
			resolved_type = str(SLOT_ID_TO_TYPE.get(int(equipped.get("slot", 0)), ""))
		if resolved_type == item_type and int(equipped.get("slot_index", 0)) == slot_index:
			return equipped
	return {}


func _clear_children(parent: Node) -> void:
	for child in parent.get_children():
		child.queue_free()


func _render_skills() -> void:
	skill_list.clear()
	for skill in _skills:
		skill_list.add_item("%s    Lv.%d" % [
			str(skill.get("skill_name", "Unknown Skill")),
			int(skill.get("level", 1)),
		])
		skill_list.set_item_metadata(skill_list.item_count - 1, skill)
	if _skills.is_empty():
		skill_name.text = "No skills learned"
		skill_details.text = ""
		skill_description.text = "Skills learned by this character will appear here."
	else:
		skill_list.select(0)
		_on_skill_selected(0)


func _on_skill_selected(index: int) -> void:
	if index < 0 or index >= skill_list.item_count:
		return
	var skill: Dictionary = skill_list.get_item_metadata(index)
	skill_name.text = "%s  Lv.%d" % [skill.get("skill_name", "Unknown Skill"), skill.get("level", 1)]
	skill_details.text = "MP %d  •  Cooldown %d  •  %s / %s  •  Damage ×%.2f" % [
		int(skill.get("mp_cost", 0)),
		int(skill.get("cooldown", 0)),
		str(skill.get("target_type", "—")),
		str(skill.get("effect_type", "—")),
		float(skill.get("damage_multiplier", 1.0)),
	]
	skill_description.text = str(skill.get("description", "No description."))


func _lookup_name(items: Array, target_id: Variant) -> String:
	if target_id == null:
		return "Unassigned"
	for item in items:
		if ApiClient.id_string(item.get("id")) == str(target_id):
			return str(item.get("name", "Unknown"))
	return "Unknown"


func _accept_response(response: Dictionary) -> bool:
	if response.get("ok", false):
		return true
	_set_loading(false, ApiClient.error_message(response, "Unable to load character data."))
	return false


func _set_loading(is_loading: bool, message: String) -> void:
	refresh_button.disabled = is_loading
	status_label.text = message


func _on_back_pressed() -> void:
	SceneRouter.go_to(SceneRouter.LAUNCHER)
