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
	# In the hub the header already shows the character, so the portrait goes.
	HubEmbed.adapt(self, [back_button, %Portrait], $Margin)
	_setup_item_tooltip()
	back_button.pressed.connect(_on_back_pressed)
	refresh_button.pressed.connect(func():
		GameCache.clear_all()
		_load_profile()
	)
	skill_list.item_selected.connect(_on_skill_selected)
	if not SceneRouter.require_session():
		return
	await _load_profile()


## Called by the hub each time this page is shown again.
func reload_page() -> void:
	await _load_profile()


func _load_profile() -> void:
	_set_loading(true, "Loading character profile...")
	var profile_response: Dictionary = await GameCache.get_json("users/profile/")
	if not _accept_response(profile_response):
		return
	_profile = profile_response.get("data", {})

	var character_response: Dictionary = await GameCache.get_json("characters/my/")
	if not _accept_response(character_response):
		return
	_character = character_response.get("data", {})
	SessionStore.character = _character

	var classes_response: Dictionary = await GameCache.get_all("classes/")
	if not _accept_response(classes_response):
		return
	_classes = ApiClient.unwrap_list(classes_response.get("data", []))

	var jobs_response: Dictionary = await GameCache.get_all("classes/jobs/")
	if not _accept_response(jobs_response):
		return
	_jobs = ApiClient.unwrap_list(jobs_response.get("data", []))

	var equipment_response: Dictionary = await GameCache.get_all("inventory/equipped/")
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
	var style := M3.box(M3.SURFACE_CONTAINER_LOWEST, M3.CORNER_MEDIUM, 4.0, M3.OUTLINE_VARIANT)
	panel.add_theme_stylebox_override("panel", style)

	var center := CenterContainer.new()
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(center)
	var empty_label := Label.new()
	empty_label.text = str(slot.short)
	empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	empty_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	empty_label.add_theme_color_override("font_color", M3.ON_SURFACE_VARIANT)
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
		style.bg_color = M3.SECONDARY_CONTAINER
		style.border_color = M3.PRIMARY
		style.set_border_width_all(2)
	panel.tooltip_text = ""
	panel.mouse_entered.connect(_show_item_tooltip.bind(equipped, panel))
	panel.mouse_exited.connect(_hide_item_tooltip)
	return panel


func _setup_item_tooltip() -> void:
	_item_tooltip = PopupPanel.new()
	_item_tooltip.name = "EquipmentTooltip"
	_item_tooltip.unresizable = true
	var style := M3.box(M3.SURFACE_CONTAINER, M3.CORNER_MEDIUM, 0.0)
	style.shadow_color = M3.with_alpha(Color.BLACK, 0.2)
	style.shadow_size = 8
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
	ItemTooltip.fill_equipment(_tooltip_box, equipped.get("item", {}), _equipped_items, "CURRENTLY EQUIPPED")


func _equipped_set_piece_count(set_data: Dictionary) -> int:
	return ItemTooltip.equipped_set_piece_count(set_data, _equipped_items)


func _set_effect_stats_text(effect: Dictionary) -> String:
	return ItemTooltip.set_effect_stats_text(effect)


func _equipment_stat_bbcode(template: Dictionary, item: Dictionary) -> String:
	return ItemTooltip.stat_bbcode(template, item)


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
		if ApiClient.id_string(item.get("id")) == ApiClient.id_string(target_id):
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
	SceneRouter.go_to(SceneRouter.HUB)
