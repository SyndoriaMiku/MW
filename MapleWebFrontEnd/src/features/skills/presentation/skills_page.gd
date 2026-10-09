class_name SkillsPage
extends Control

## The character's skills: what each does at its level, what the next level
## brings and needs, and the skills still to unlock. Upgrades that need
## materials are bought here; the others happen on level-up by themselves.

var _skills: Array = []
var _learnable: Array = []
var _owned: Dictionary = {}
var _material_names: Dictionary = {}
var _selected_key := ""
var _busy := false
var _character_level := 1

var _status: Label
var _list: VBoxContainer
var _detail: VBoxContainer
var _name := Label.new()
var _chips := HBoxContainer.new()
var _description := Label.new()
var _now_title := Label.new()
var _now_text := Label.new()
var _next_box := VBoxContainer.new()
var _next_text := Label.new()
var _materials := VBoxContainer.new()
var _state := Label.new()
var _upgrade_button := Button.new()
var _empty := Label.new()


func _init() -> void:
	name = "SkillsPage"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var column := HubWidgets.page_column(self)
	var header := HubWidgets.header("Skills", load_skills)
	_status = header.status
	column.add_child(header.row)
	var content := HBoxContainer.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 16)
	column.add_child(content)
	_list = HubWidgets.scroll_list(content, 400)
	_empty.text = "No skills yet."
	_empty.theme_type_variation = &"MutedLabel"
	_detail = HubWidgets.detail_card(content)
	_build_detail()


## The empty-state label is out of the tree while the list has rows.
func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and is_instance_valid(_empty) and _empty.get_parent() == null:
		_empty.free()


func _build_detail() -> void:
	_name.add_theme_font_size_override("font_size", M3.HEADLINE_MEDIUM)
	_detail.add_child(_name)
	_chips.add_theme_constant_override("separation", 8)
	_detail.add_child(_chips)
	_description.theme_type_variation = &"MutedLabel"
	_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_description)
	_now_title.theme_type_variation = &"AccentLabel"
	_detail.add_child(_now_title)
	_now_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_now_text)
	_next_box.add_theme_constant_override("separation", 6)
	_detail.add_child(_next_box)
	_next_box.add_child(HubWidgets.section_label("Next level"))
	_next_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_next_box.add_child(_next_text)
	_materials.add_theme_constant_override("separation", 4)
	_next_box.add_child(_materials)
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_child(spacer)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 12)
	_detail.add_child(actions)
	_state.theme_type_variation = &"MutedLabel"
	_state.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_state.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_state.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	actions.add_child(_state)
	_upgrade_button.name = "UpgradeButton"
	_upgrade_button.text = "Upgrade"
	_upgrade_button.theme_type_variation = &"PrimaryButton"
	_upgrade_button.custom_minimum_size = Vector2(180, 48)
	_upgrade_button.icon = IconTexture.make("upgrade", M3.ON_PRIMARY)
	_upgrade_button.pressed.connect(_on_upgrade_pressed)
	actions.add_child(_upgrade_button)


## Called by the hub when the page is created or shown again.
func load_skills() -> void:
	if _busy:
		return
	_set_busy(true, "Loading skills...")
	var character_response: Dictionary = await GameCache.get_json("characters/my/")
	var skills_response: Dictionary = await GameCache.get_json("characters/my/skills/")
	var learnable_response: Dictionary = await GameCache.get_json("skills/learnable/")
	var inventory_response: Dictionary = await GameCache.get_all("inventory/")
	if not is_inside_tree():
		return
	if not skills_response.get("ok", false):
		_set_busy(false, ApiClient.error_message(skills_response, "Unable to load skills."))
		return
	if character_response.get("ok", false):
		_character_level = int(character_response.data.get("level", 1))
	_skills = ApiClient.unwrap_list(skills_response.data)
	_skills.sort_custom(func(a, b): return _sort_key(a) < _sort_key(b))
	_learnable = ApiClient.unwrap_list(learnable_response.get("data", [])) if learnable_response.get("ok", false) else []
	_owned = SkillRules.owned_counts(inventory_response.get("data", [])) if inventory_response.get("ok", false) else {}
	await _load_material_names()
	if not is_inside_tree():
		return
	if _find_selected().is_empty():
		_selected_key = _key_for(_skills[0], false) if not _skills.is_empty() else (_key_for(_learnable[0], true) if not _learnable.is_empty() else "")
	_set_busy(false, "")
	_render()


## How many owned skills can be upgraded right now (for a badge).
func upgradable_count() -> int:
	var count := 0
	for skill in _skills:
		if SkillRules.upgrade_state(skill, _character_level, _owned).kind == "ready":
			count += 1
	return count


## Basic attack first, then active skills, then passives, each by name.
static func _sort_key(skill: Dictionary) -> String:
	var group := "0" if bool(skill.get("is_basic_attack", false)) else ("2" if bool(skill.get("is_passive", false)) else "1")
	return group + str(skill.get("skill_name", "")).to_lower()


func _load_material_names() -> void:
	for skill in _skills:
		var next: Variant = skill.get("next_upgrade")
		if not next is Dictionary:
			continue
		for material in next.get("required_materials", []):
			var template_id := ApiClient.id_string(material.get("item_template_id"))
			if template_id.is_empty() or _material_names.has(template_id):
				continue
			var response: Dictionary = await GameCache.get_json("items/templates/%s/" % template_id)
			_material_names[template_id] = str(response.data.get("name", "Item #" + template_id)) if response.get("ok", false) and response.data is Dictionary else "Item #" + template_id


func _render() -> void:
	HubWidgets.clear(_list, [_empty])
	if _skills.is_empty() and _learnable.is_empty():
		_list.add_child(_empty)
	if not _skills.is_empty():
		_list.add_child(HubWidgets.section_label("Learned"))
	for skill in _skills:
		var state := SkillRules.upgrade_state(skill, _character_level, _owned)
		var kind_text := "Passive" if bool(skill.get("is_passive", false)) else ("Basic attack" if bool(skill.get("is_basic_attack", false)) else "Active")
		var card := HubWidgets.list_card(
			SkillRules.icon_for(skill), str(skill.get("skill_name", "Skill")),
			"Lv. %d  •  %s" % [int(skill.get("level", 1)), kind_text],
			_key_for(skill, false) == _selected_key, false,
			"Upgrade" if state.kind == "ready" else "", M3.SUCCESS
		)
		card.pressed.connect(_select.bind(_key_for(skill, false)))
		_list.add_child(card)
	if not _learnable.is_empty():
		_list.add_child(HubWidgets.section_label("Unlocks later"))
	for skill in _learnable:
		var card := HubWidgets.list_card(
			"lock", str(skill.get("name", "Skill")),
			"Unlocks at character level %d" % int(skill.get("unlock_level", skill.get("required_level", 1))),
			_key_for(skill, true) == _selected_key, true
		)
		card.pressed.connect(_select.bind(_key_for(skill, true)))
		_list.add_child(card)
	_render_detail()


func _render_detail() -> void:
	var selected := _find_selected()
	_detail.get_parent().visible = not selected.is_empty()
	if selected.is_empty():
		return
	var learnable := _selected_key.begins_with("learn:")
	HubWidgets.clear(_chips)
	_name.text = str(selected.get("skill_name", selected.get("name", "Skill")))
	if not learnable:
		_add_chip("military_tech", "Lv. %d" % int(selected.get("level", 1)))
	if bool(selected.get("is_passive", false)) or str(selected.get("effect_type", "")) == "PASSIVE":
		_add_chip("shield", "Passive")
	else:
		_add_chip("water_drop", "%d MP" % int(selected.get("mp_cost", 0)))
		_add_chip("timer", "Cooldown %d" % int(selected.get("cooldown", 0)))
		_add_chip("groups", SkillRules.TARGET_LABELS.get(str(selected.get("target_type", "")), str(selected.get("target_type", ""))))
	_description.text = str(selected.get("description", "")).strip_edges()
	_description.visible = not _description.text.is_empty()
	if learnable:
		_now_title.text = "Not learned yet"
		_now_text.text = "Unlocks by itself when your character reaches level %d." % int(selected.get("unlock_level", selected.get("required_level", 1)))
		_next_box.visible = false
		_state.text = ""
		_upgrade_button.visible = false
		return
	_now_title.text = "Now"
	var bonus := float(selected.get("bonus_final_damage", 0.0))
	_now_text.text = "Damage %s%s" % [
		SkillRules.multiplier_text(selected.get("damage_multiplier", 1.0)),
		"   •   Final damage +%d%% from passives" % roundi(bonus * 100.0) if bonus > 0.0 else "",
	]
	_now_text.visible = not bool(selected.get("is_passive", false))
	var next: Variant = selected.get("next_upgrade")
	_next_box.visible = next is Dictionary
	HubWidgets.clear(_materials)
	if next is Dictionary:
		_next_text.text = "Lv. %d  •  Damage %s  •  Character level %d" % [
			int(next.get("skill_level", 0)), SkillRules.multiplier_text(next.get("damage_multiplier", 1.0)), int(next.get("required_char_level", 1)),
		]
		for material in next.get("required_materials", []):
			var template_id := ApiClient.id_string(material.get("item_template_id"))
			var have := int(_owned.get(template_id, 0))
			var need := int(material.get("quantity", 0))
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 8)
			row.add_child(M3.icon_label("check_circle" if have >= need else "radio_button_unchecked", 18, M3.SUCCESS if have >= need else M3.ON_SURFACE_VARIANT))
			var label := Label.new()
			label.text = "%s   %d / %d" % [_material_names.get(template_id, "Item #" + template_id), have, need]
			label.theme_type_variation = &"SuccessLabel" if have >= need else &"MutedLabel"
			row.add_child(label)
			_materials.add_child(row)
	var state := SkillRules.upgrade_state(selected, _character_level, _owned)
	_state.text = state.text
	_upgrade_button.visible = state.kind in ["ready", "materials", "level"]
	_upgrade_button.disabled = _busy or state.kind != "ready"


func _add_chip(icon_name: String, text: String) -> void:
	_chips.add_child(HubWidgets.chip(icon_name, text).chip)


func _select(key: String) -> void:
	_selected_key = key
	_render()


func _on_upgrade_pressed() -> void:
	var skill := _find_selected()
	if _busy or skill.is_empty() or _selected_key.begins_with("learn:"):
		return
	if SkillRules.upgrade_state(skill, _character_level, _owned).kind != "ready":
		return
	_set_busy(true, "Upgrading %s..." % str(skill.get("skill_name", "the skill")))
	var response: Dictionary = await ApiClient.post_json("characters/my/skills/%s/upgrade/" % ApiClient.id_string(skill.get("character_skill_id", skill.get("id"))))
	if not is_inside_tree():
		return
	var message := ApiClient.error_message(response, "Unable to upgrade the skill.") if not response.get("ok", false) else str(response.data.get("detail", "Skill upgraded."))
	_busy = false
	await load_skills()
	_status.text = message


func _set_busy(value: bool, message: String) -> void:
	_busy = value
	_status.text = message
	if not _skills.is_empty() or not _learnable.is_empty():
		_render_detail()


func _find_selected() -> Dictionary:
	for skill in _skills:
		if _key_for(skill, false) == _selected_key:
			return skill
	for skill in _learnable:
		if _key_for(skill, true) == _selected_key:
			return skill
	return {}


static func _key_for(skill: Dictionary, learnable: bool) -> String:
	if learnable:
		return "learn:" + ApiClient.id_string(skill.get("id"))
	return "own:" + ApiClient.id_string(skill.get("character_skill_id", skill.get("id")))
