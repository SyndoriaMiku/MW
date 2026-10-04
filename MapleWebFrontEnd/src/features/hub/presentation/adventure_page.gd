class_name AdventurePage
extends Control

## Pick a normal dungeon and enter it. Dungeons are listed in the order set in
## Studio (the API's `order`). Dungeons above the character's level are
## locked; entering needs enough stamina and no battle in progress (resume it
## instead).

signal battle_started
signal stamina_changed

var _dungeons: Array = []
var _selected: Dictionary = {}
var _character: Dictionary = {}
var _active_battle: Dictionary = {}
var _stamina := 0
var _busy := false

var _list := VBoxContainer.new()
var _detail_name := Label.new()
var _detail_description := Label.new()
var _detail_level := Label.new()
var _detail_cost := Label.new()
var _detail_reason := Label.new()
var _enter_button := Button.new()
var _resume_banner := PanelContainer.new()
var _resume_text := Label.new()
var _status := Label.new()
var _empty := Label.new()
var _detail_card := PanelContainer.new()


func _init() -> void:
	name = "AdventurePage"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 20)
	add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	margin.add_child(column)

	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	column.add_child(header)
	var title := Label.new()
	title.text = "Adventure"
	title.theme_type_variation = &"HeadlineLabel"
	header.add_child(title)
	_status.theme_type_variation = &"MutedLabel"
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_status.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	header.add_child(_status)
	var refresh := Button.new()
	refresh.name = "RefreshButton"
	refresh.text = "Refresh"
	refresh.theme_type_variation = &"TextButton"
	refresh.icon = IconTexture.make("refresh", M3.PRIMARY, 20)
	refresh.pressed.connect(func():
		GameCache.clear_all()
		load_dungeons()
	)
	header.add_child(refresh)

	_resume_banner.visible = false
	_resume_banner.add_theme_stylebox_override("panel", M3.box(M3.ERROR_CONTAINER, M3.CORNER_LARGE, 12.0))
	column.add_child(_resume_banner)
	var banner_row := HBoxContainer.new()
	banner_row.add_theme_constant_override("separation", 12)
	_resume_banner.add_child(banner_row)
	banner_row.add_child(M3.icon_label("swords", 22, M3.ON_ERROR_CONTAINER))
	_resume_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_resume_text.add_theme_color_override("font_color", M3.ON_ERROR_CONTAINER)
	_resume_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	banner_row.add_child(_resume_text)
	var resume := Button.new()
	resume.name = "ResumeButton"
	resume.text = "Resume"
	resume.theme_type_variation = &"DangerButton"
	resume.pressed.connect(func(): SceneRouter.go_to(SceneRouter.BATTLE))
	banner_row.add_child(resume)

	var content := HBoxContainer.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 16)
	column.add_child(content)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(420, 0)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	content.add_child(scroll)
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 8)
	scroll.add_child(_list)
	_empty.text = "No dungeon is open yet."
	_empty.theme_type_variation = &"MutedLabel"
	_empty.visible = false
	_list.add_child(_empty)

	_detail_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_detail_card.add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER_LOWEST, M3.CORNER_EXTRA_LARGE, 24.0))
	content.add_child(_detail_card)
	var detail := VBoxContainer.new()
	detail.add_theme_constant_override("separation", 12)
	_detail_card.add_child(detail)
	_detail_name.add_theme_font_size_override("font_size", M3.HEADLINE_MEDIUM)
	detail.add_child(_detail_name)
	var chips := HBoxContainer.new()
	chips.add_theme_constant_override("separation", 8)
	detail.add_child(chips)
	chips.add_child(_chip(_detail_level, "military_tech"))
	chips.add_child(_chip(_detail_cost, "bolt"))
	_detail_description.theme_type_variation = &"MutedLabel"
	_detail_description.add_theme_font_size_override("font_size", M3.BODY_LARGE)
	_detail_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail_description.size_flags_vertical = Control.SIZE_EXPAND_FILL
	detail.add_child(_detail_description)
	_detail_reason.theme_type_variation = &"ErrorLabel"
	_detail_reason.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail.add_child(_detail_reason)
	_enter_button.name = "EnterButton"
	_enter_button.text = "Enter dungeon"
	_enter_button.theme_type_variation = &"PrimaryButton"
	_enter_button.custom_minimum_size = Vector2(220, 48)
	_enter_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	_enter_button.icon = IconTexture.make("play_arrow", M3.ON_PRIMARY)
	_enter_button.pressed.connect(_on_enter_pressed)
	detail.add_child(_enter_button)
	_render_detail()


func _chip(label: Label, icon_name: String) -> PanelContainer:
	var chip := PanelContainer.new()
	chip.add_theme_stylebox_override("panel", M3.box(Color.TRANSPARENT, M3.CORNER_SMALL, 6.0, M3.OUTLINE_VARIANT))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	chip.add_child(row)
	row.add_child(M3.icon_label(icon_name, 18, M3.PRIMARY))
	label.add_theme_font_override("font", M3.FONT_MEDIUM)
	label.add_theme_font_size_override("font_size", M3.LABEL_LARGE)
	label.add_theme_color_override("font_color", M3.ON_SURFACE_VARIANT)
	row.add_child(label)
	return chip


## The hub hands over what it already knows; `stamina` is the regenerated value.
func set_context(character: Dictionary, stamina: int, active_battle: Dictionary) -> void:
	_character = character
	_stamina = stamina
	_active_battle = active_battle
	_resume_banner.visible = not active_battle.is_empty()
	if not active_battle.is_empty():
		_resume_text.text = "A battle is in progress (turn %d). Finish it before entering another dungeon." % int(active_battle.get("turn_count", 1))
	_render_list()
	_render_detail()


func load_dungeons() -> void:
	if _busy:
		return
	_set_busy(true, "Loading dungeons...")
	var response: Dictionary = await GameCache.get_all("world/normal-dungeons/")
	if not is_inside_tree():
		return
	if not response.get("ok", false):
		_set_busy(false, ApiClient.error_message(response, "Unable to load dungeons."))
		return
	_dungeons = ApiClient.unwrap_list(response.get("data", []))
	_dungeons = sorted_by_order(_dungeons)
	if _selected.is_empty() or _find(_selected.get("id")).is_empty():
		_selected = _first_open()
	else:
		_selected = _find(_selected.get("id"))
	_render_list()
	_set_busy(false, "")


## Dungeons in their Studio order (`order`, then level, then id, as the
## backend sorts them). Servers without `order` keep the level order.
static func sorted_by_order(dungeons: Array) -> Array:
	var result := dungeons.duplicate()
	result.sort_custom(func(a, b):
		for key in ["order", "required_level", "id"]:
			var left := float(a.get(key, 0))
			var right := float(b.get(key, 0))
			if left != right:
				return left < right
		return false
	)
	return result


## Why the selected dungeon cannot be entered right now, "" when it can.
static func block_reason(dungeon: Dictionary, level: int, stamina: int, has_active_battle: bool) -> String:
	if dungeon.is_empty():
		return "Pick a dungeon."
	if has_active_battle:
		return "Finish your current battle first."
	if level < int(dungeon.get("required_level", 1)):
		return "Requires level %d." % int(dungeon.get("required_level", 1))
	if stamina < int(dungeon.get("stamina_cost", 0)):
		return "Not enough stamina (%d needed)." % int(dungeon.get("stamina_cost", 0))
	return ""


func _render_list() -> void:
	for child in _list.get_children():
		if child != _empty:
			_list.remove_child(child)
			child.queue_free()
	_empty.visible = _dungeons.is_empty() and not _busy
	var level := int(_character.get("level", 1))
	for dungeon in _dungeons:
		_list.add_child(_dungeon_card(dungeon, level))
	_render_detail()


func _dungeon_card(dungeon: Dictionary, level: int) -> Button:
	var locked := level < int(dungeon.get("required_level", 1))
	var selected := ApiClient.id_string(dungeon.get("id")) == ApiClient.id_string(_selected.get("id"))
	var card := Button.new()
	card.name = "Dungeon%s" % ApiClient.id_string(dungeon.get("id"))
	card.custom_minimum_size = Vector2(0, 72)
	card.toggle_mode = true
	card.button_pressed = selected
	card.focus_mode = Control.FOCUS_NONE
	var base := M3.SECONDARY_CONTAINER if selected else M3.SURFACE_CONTAINER_LOWEST
	var content := M3.ON_SECONDARY_CONTAINER if selected else M3.ON_SURFACE
	for state in ["normal", "hover", "pressed", "hover_pressed"]:
		var opacity := M3.HOVER_OPACITY if state.begins_with("hover") else 0.0
		card.add_theme_stylebox_override(state, M3.box(M3.layered(base, content, opacity), M3.CORNER_LARGE, 12.0))
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 12)
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(row)
	var badge := PanelContainer.new()
	badge.custom_minimum_size = Vector2(48, 48)
	badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	badge.add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER_HIGHEST if locked else M3.PRIMARY_CONTAINER, M3.CORNER_MEDIUM, 0.0))
	badge.add_child(M3.icon_label("lock" if locked else "castle", 24, M3.ON_SURFACE_VARIANT if locked else M3.ON_PRIMARY_CONTAINER))
	row.add_child(badge)
	var text := VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.alignment = BoxContainer.ALIGNMENT_CENTER
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_theme_constant_override("separation", 2)
	row.add_child(text)
	var title := Label.new()
	title.text = str(dungeon.get("name", "Dungeon"))
	title.theme_type_variation = &"TitleLabel"
	title.add_theme_color_override("font_color", content if not locked else M3.with_alpha(M3.ON_SURFACE, M3.DISABLED_CONTENT_OPACITY + 0.2))
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(title)
	var meta := Label.new()
	meta.text = "Lv. %d+   •   %d stamina" % [int(dungeon.get("required_level", 1)), int(dungeon.get("stamina_cost", 0))]
	meta.theme_type_variation = &"MutedLabel"
	meta.add_theme_font_size_override("font_size", M3.BODY_SMALL)
	meta.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(meta)
	card.pressed.connect(_select.bind(dungeon))
	return card


func _select(dungeon: Dictionary) -> void:
	_selected = dungeon
	_render_list()


func _render_detail() -> void:
	var has_dungeon := not _selected.is_empty()
	_detail_card.visible = has_dungeon or not _dungeons.is_empty()
	_detail_name.text = str(_selected.get("name", "Pick a dungeon"))
	_detail_description.text = str(_selected.get("description", "")).strip_edges()
	if _detail_description.text.is_empty():
		_detail_description.text = "Enter the dungeon and defeat every enemy." if has_dungeon else "Choose a dungeon from the list."
	_detail_level.text = "Level %d+" % int(_selected.get("required_level", 1))
	_detail_cost.text = "%d stamina  (you have %d)" % [int(_selected.get("stamina_cost", 0)), _stamina]
	var reason := block_reason(_selected, int(_character.get("level", 1)), _stamina, not _active_battle.is_empty())
	_detail_reason.text = reason if has_dungeon else ""
	_detail_reason.visible = not _detail_reason.text.is_empty()
	_enter_button.disabled = _busy or not reason.is_empty()


func _on_enter_pressed() -> void:
	if _busy or not block_reason(_selected, int(_character.get("level", 1)), _stamina, not _active_battle.is_empty()).is_empty():
		return
	_set_busy(true, "Entering %s..." % str(_selected.get("name", "the dungeon")))
	var response: Dictionary = await ApiClient.post_json("world/normal-dungeons/%s/enter/" % ApiClient.id_string(_selected.get("id")))
	if not is_inside_tree():
		return
	if not response.get("ok", false):
		_set_busy(false, ApiClient.error_message(response, "Unable to enter the dungeon."))
		stamina_changed.emit()
		return
	SessionStore.active_battle_id = ApiClient.id_string(response.get("data", {}).get("combat_instance_id"))
	if SessionStore.active_battle_id.is_empty():
		_set_busy(false, "The server did not return a battle.")
		return
	battle_started.emit()
	SceneRouter.go_to(SceneRouter.BATTLE)


func _set_busy(value: bool, message: String) -> void:
	_busy = value
	_status.text = message
	_render_detail()


func _find(id: Variant) -> Dictionary:
	for dungeon in _dungeons:
		if ApiClient.id_string(dungeon.get("id")) == ApiClient.id_string(id):
			return dungeon
	return {}


## The open dungeon with the highest required level (the first such one in
## the list), else the first dungeon.
func _first_open() -> Dictionary:
	var level := int(_character.get("level", 1))
	var best: Dictionary = {}
	for dungeon in _dungeons:
		var required := int(dungeon.get("required_level", 1))
		if required <= level and (best.is_empty() or required > int(best.get("required_level", 1))):
			best = dungeon
	return best if not best.is_empty() else (_dungeons[0] if not _dungeons.is_empty() else {})
