class_name HomePage
extends Control

## The hub's home: the game's (or the running event's) key art, the running
## rate events and a way into battle — resume the active one, or go pick a
## dungeon.

signal adventure_requested
signal resume_requested
signal quests_requested

## Drop key art here to replace the drawn background.
const BACKGROUND_PATH := "res://assets/ui/home_background.png"

var _art := HomeArt.new()
var _greeting := Label.new()
var _events_box := VBoxContainer.new()
var _quest_card := Button.new()
var _quest_title := Label.new()
var _quest_meta := Label.new()
var _resume_card := PanelContainer.new()
var _resume_details := Label.new()
var _adventure_button := Button.new()
var _events: Array = []
var _server_offset := 0.0


func _init() -> void:
	name = "HomePage"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	clip_contents = true
	if ResourceLoader.exists(BACKGROUND_PATH):
		var picture := TextureRect.new()
		picture.texture = load(BACKGROUND_PATH)
		picture.set_anchors_preset(Control.PRESET_FULL_RECT)
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		picture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
		picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(picture)
	else:
		_art.set_anchors_preset(Control.PRESET_FULL_RECT)
		add_child(_art)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 32)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(margin)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 24)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(row)

	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(500, 0)
	left.add_theme_constant_override("separation", 12)
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(left)
	var eyebrow := Label.new()
	eyebrow.text = "MAPLE WORLD"
	eyebrow.theme_type_variation = &"AccentLabel"
	eyebrow.add_theme_color_override("font_color", M3.ON_PRIMARY_CONTAINER)
	left.add_child(eyebrow)
	_greeting.text = "Welcome back"
	_greeting.add_theme_font_size_override("font_size", M3.DISPLAY_SMALL)
	_greeting.add_theme_color_override("font_color", M3.ON_PRIMARY_CONTAINER)
	left.add_child(_greeting)
	var events_title := Label.new()
	events_title.text = "Events"
	events_title.theme_type_variation = &"TitleLabel"
	events_title.add_theme_color_override("font_color", M3.ON_PRIMARY_CONTAINER)
	left.add_child(events_title)
	_events_box.add_theme_constant_override("separation", 8)
	left.add_child(_events_box)
	_build_quest_card(left)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(spacer)

	var right := VBoxContainer.new()
	right.alignment = BoxContainer.ALIGNMENT_END
	right.add_theme_constant_override("separation", 12)
	right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(right)
	_build_resume_card(right)
	_adventure_button.name = "AdventureButton"
	_adventure_button.text = "Adventure"
	_adventure_button.custom_minimum_size = Vector2(0, 80)
	_adventure_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	_adventure_button.add_theme_font_size_override("font_size", M3.TITLE_MEDIUM)
	_adventure_button.add_theme_constant_override("h_separation", 12)
	_adventure_button.icon = _icon_texture("swords", M3.ON_PRIMARY_CONTAINER)
	for state in ["normal", "hover", "pressed", "hover_pressed"]:
		var opacity: float = {"normal": 0.0, "hover": M3.HOVER_OPACITY, "pressed": M3.PRESS_OPACITY, "hover_pressed": M3.PRESS_OPACITY}[state]
		var style := M3.box(M3.layered(M3.PRIMARY_CONTAINER, M3.ON_PRIMARY_CONTAINER, opacity), M3.CORNER_LARGE + 4, 0.0)
		style.content_margin_left = 28
		style.content_margin_right = 32
		style.shadow_color = M3.with_alpha(Color.BLACK, 0.18)
		style.shadow_size = 6
		style.shadow_offset = Vector2(0, 3)
		_adventure_button.add_theme_stylebox_override(state, style)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		_adventure_button.add_theme_color_override(state, M3.ON_PRIMARY_CONTAINER)
	_adventure_button.pressed.connect(adventure_requested.emit)
	right.add_child(_adventure_button)
	_render_events()


func _build_resume_card(parent: Control) -> void:
	_resume_card.name = "ResumeCard"
	_resume_card.visible = false
	_resume_card.custom_minimum_size = Vector2(320, 0)
	_resume_card.add_theme_stylebox_override("panel", M3.box(M3.with_alpha(M3.SURFACE_CONTAINER_LOWEST, 0.92), M3.CORNER_CARD, 16.0))
	parent.add_child(_resume_card)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	_resume_card.add_child(box)
	var title_row := HBoxContainer.new()
	title_row.add_theme_constant_override("separation", 8)
	box.add_child(title_row)
	title_row.add_child(M3.icon_label("swords", 22, M3.ERROR))
	var title := Label.new()
	title.text = "Battle in progress"
	title.theme_type_variation = &"TitleLabel"
	title_row.add_child(title)
	_resume_details.theme_type_variation = &"MutedLabel"
	box.add_child(_resume_details)
	var resume := Button.new()
	resume.name = "ResumeButton"
	resume.text = "Resume battle"
	resume.theme_type_variation = &"PrimaryButton"
	resume.icon = _icon_texture("play_arrow", M3.ON_PRIMARY)
	resume.pressed.connect(resume_requested.emit)
	box.add_child(resume)


## A card that opens Quests; it says how many wait to be claimed.
func _build_quest_card(parent: Control) -> void:
	var title := Label.new()
	title.text = "Quests"
	title.theme_type_variation = &"TitleLabel"
	title.add_theme_color_override("font_color", M3.ON_PRIMARY_CONTAINER)
	parent.add_child(title)
	_quest_card.name = "QuestCard"
	_quest_card.custom_minimum_size = Vector2(0, 72)
	_quest_card.focus_mode = Control.FOCUS_NONE
	for state in ["normal", "hover", "pressed", "hover_pressed"]:
		var opacity := M3.HOVER_OPACITY if state.begins_with("hover") else 0.0
		_quest_card.add_theme_stylebox_override(state, M3.box(M3.layered(M3.with_alpha(M3.SURFACE_CONTAINER_LOWEST, 0.9), M3.ON_SURFACE, opacity), M3.CORNER_CARD, 14.0))
	_quest_card.pressed.connect(quests_requested.emit)
	parent.add_child(_quest_card)
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 14)
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_quest_card.add_child(row)
	row.add_child(HubWidgets.badge("task_alt", M3.PRIMARY_CONTAINER, M3.ON_PRIMARY_CONTAINER, 44))
	var text := VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.alignment = BoxContainer.ALIGNMENT_CENTER
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(text)
	_quest_title.theme_type_variation = &"TitleLabel"
	_quest_title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(_quest_title)
	_quest_meta.theme_type_variation = &"MutedLabel"
	_quest_meta.add_theme_font_size_override("font_size", M3.BODY_SMALL)
	_quest_meta.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(_quest_meta)
	row.add_child(M3.icon_label("arrow_forward", 22, M3.ON_SURFACE_VARIANT))
	set_quests(0, 0)


## `ready`: quests waiting to be claimed; `active`: quests in progress.
func set_quests(ready: int, active: int) -> void:
	if ready > 0:
		_quest_title.text = "%d %s ready to claim" % [ready, "quest" if ready == 1 else "quests"]
	elif active > 0:
		_quest_title.text = "%d %s in progress" % [active, "quest" if active == 1 else "quests"]
	else:
		_quest_title.text = "No quest to do"
	_quest_meta.text = "Open your quests"


func set_character_name(character_name: String) -> void:
	_greeting.text = "Welcome back, %s" % character_name if not character_name.is_empty() else "Welcome back"


## `battle`: the active combat from the bootstrap, or {} for none.
func set_active_battle(battle: Dictionary) -> void:
	_resume_card.visible = not battle.is_empty()
	_adventure_button.visible = battle.is_empty()
	if not battle.is_empty():
		var phase := str(battle.get("turn_phase", "player_phase")).replace("_", " ").capitalize()
		_resume_details.text = "Turn %d  •  %s" % [int(battle.get("turn_count", 1)), phase]


## `events`: running rate events; `server_offset`: server clock minus local
## clock, for the time left.
func set_events(events: Array, server_offset: float) -> void:
	_events = events
	_server_offset = server_offset
	_render_events()


func _render_events() -> void:
	for child in _events_box.get_children():
		_events_box.remove_child(child)
		child.queue_free()
	if _events.is_empty():
		var empty := Label.new()
		empty.text = "No event is running right now."
		empty.add_theme_color_override("font_color", M3.with_alpha(M3.ON_PRIMARY_CONTAINER, 0.75))
		_events_box.add_child(empty)
		return
	for event in _events.slice(0, 3):
		_events_box.add_child(_event_card(event))


func _event_card(event: Dictionary) -> PanelContainer:
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", M3.box(M3.with_alpha(M3.SURFACE_CONTAINER_LOWEST, 0.9), M3.CORNER_CARD, 14.0))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	card.add_child(row)
	var badge := PanelContainer.new()
	badge.custom_minimum_size = Vector2(44, 44)
	badge.add_theme_stylebox_override("panel", M3.box(M3.TERTIARY_CONTAINER, M3.CORNER_MEDIUM, 0.0))
	badge.add_child(M3.icon_label("celebration", 24, M3.ON_TERTIARY_CONTAINER))
	badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(badge)
	var text := VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.add_theme_constant_override("separation", 2)
	row.add_child(text)
	var title := Label.new()
	title.text = str(event.get("name", "Event"))
	title.theme_type_variation = &"TitleLabel"
	text.add_child(title)
	var details := Label.new()
	details.text = event_summary(event, Time.get_unix_time_from_system() + _server_offset)
	details.theme_type_variation = &"MutedLabel"
	details.add_theme_font_size_override("font_size", M3.BODY_SMALL)
	details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.add_child(details)
	return card


## "EXP +100%  •  Drop +50%  •  Ends in 2d 4h".
static func event_summary(event: Dictionary, now: float) -> String:
	var parts: Array[String] = []
	for pair in [["exp_rate_bonus", "EXP"], ["lumis_rate_bonus", "Lumis"], ["drop_rate_bonus", "Drop"], ["epic_drop_rate_bonus", "Epic drop"]]:
		var bonus := float(event.get(pair[0], 0.0))
		if bonus > 0.0:
			parts.append("%s +%s%%" % [pair[1], str(snappedf(bonus, 0.1)).trim_suffix(".0")])
	var end_time := StaminaClock.iso_to_unix(str(event.get("end_time", "")))
	if end_time > 0.0:
		parts.append("Ends in %s" % time_left_text(int(end_time - now)))
	if parts.is_empty():
		parts.append(str(event.get("description", "")))
	return "  •  ".join(parts)


static func time_left_text(seconds: int) -> String:
	if seconds <= 0:
		return "moments"
	if seconds >= 86400:
		return "%dd %dh" % [seconds / 86400, (seconds % 86400) / 3600]
	if seconds >= 3600:
		return "%dh %02dm" % [seconds / 3600, (seconds % 3600) / 60]
	return "%dm" % maxi(1, seconds / 60)


## Material Symbols rendered to a texture, for Button.icon.
static func _icon_texture(icon_name: String, color: Color, icon_size: int = 24) -> Texture2D:
	return IconTexture.make(icon_name, color, icon_size)


## The drawn key art used until real art is added: a sky-to-sea gradient,
## soft light and a large maple-forest mark.
class HomeArt:
	extends Control

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var middle := M3.PRIMARY_CONTAINER.lerp(M3.TERTIARY_CONTAINER, 0.5)
		draw_polygon(
			PackedVector2Array([Vector2.ZERO, Vector2(size.x, 0), size, Vector2(0, size.y)]),
			PackedColorArray([M3.PRIMARY_CONTAINER, middle, M3.TERTIARY_CONTAINER, middle])
		)
		var glows := [
			[Vector2(0.78, 0.2), 0.32, 0.35], [Vector2(0.92, 0.85), 0.24, 0.25],
			[Vector2(0.55, 1.05), 0.3, 0.2], [Vector2(0.05, 0.05), 0.18, 0.18],
		]
		for glow in glows:
			draw_circle(size * glow[0], size.y * glow[1] * 1.6, M3.with_alpha(M3.SURFACE_CONTAINER_LOWEST, glow[2]))
		var font: Font = M3.ICON_FONT
		var mark := M3.icon("forest")
		var mark_size := int(size.y * 0.9)
		draw_string(font, Vector2(size.x * 0.6, size.y * 0.98), mark, HORIZONTAL_ALIGNMENT_LEFT, -1, mark_size, M3.with_alpha(M3.PRIMARY, 0.12))
