class_name AuroraChoicePanel
extends Control

## Blocking overlay for an unconfirmed Aurora roll (an item's
## pending_aurora_roll from the inventory API). It covers the whole screen and
## has no close button: the player must keep the current lines or take the new
## ones. A roll that raised the Aurora level can only be taken.
##
## REROLL_CHOICE compares the current lines with the new ones; REROLL_TRIPLE_CHOICE
## asks to pick `select_count` lines from the choices.

signal decided(action: String, selected_temp_ids: Array)

const TRIPLE_CHOICE := "REROLL_TRIPLE_CHOICE"
const NEW_COLOR := M3.SUCCESS
const TIER_UP_COLOR := M3.GOLD

@onready var title_label: Label = %ChoiceTitle
@onready var subtitle_label: Label = %ChoiceSubtitle
@onready var notice_label: Label = %ChoiceNotice
@onready var current_title: Label = %CurrentTitle
@onready var current_lines: VBoxContainer = %CurrentLines
@onready var new_title: Label = %NewTitle
@onready var new_lines: GridContainer = %NewLines
@onready var error_label: Label = %ChoiceError
@onready var keep_button: Button = %KeepButton
@onready var take_button: Button = %TakeButton

var _roll: Dictionary = {}
var _selected: Array = []
var _busy := false


func _ready() -> void:
	visible = false
	keep_button.pressed.connect(func(): _decide("keep_old"))
	take_button.pressed.connect(_on_take_pressed)


## Escape and clicks outside never dismiss the choice.
func _gui_input(event: InputEvent) -> void:
	accept_event()


func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()


func is_open() -> bool:
	return visible


func show_roll(item: Dictionary) -> void:
	_roll = item.get("pending_aurora_roll", {}) if item.get("pending_aurora_roll") is Dictionary else {}
	_selected = []
	_busy = false
	error_label.text = ""
	var template: Dictionary = item.get("template", {})
	var current_level := int(_roll.get("current_aurora_level", item.get("aurora_level", 0)))
	var new_level := int(_roll.get("new_aurora_level", current_level))
	var tier_up := must_take_new()

	title_label.text = "AURORA TIER UP!" if tier_up else "CHOOSE YOUR AURORA LINES"
	title_label.add_theme_color_override("font_color", TIER_UP_COLOR if tier_up else M3.ON_SURFACE)
	subtitle_label.text = "%s  •  Aurora %d%s" % [str(template.get("name", "Item")), current_level, "  →  %d" % new_level if new_level != current_level else ""]
	if tier_up:
		notice_label.text = "The higher Aurora level only comes with the new lines, so they must be taken."
	elif is_triple_choice():
		notice_label.text = "Pick %s for the item, or keep the current ones. You must decide before doing anything else." % _lines_text(select_count())
	else:
		notice_label.text = "Keep the current lines or take the new ones. You must decide before doing anything else."

	current_title.text = "CURRENT  •  AURORA %d" % current_level
	_fill_lines(current_lines, item.get("aurora_lines", []), M3.ON_SURFACE)
	for child in new_lines.get_children():
		new_lines.remove_child(child)
		child.queue_free()
	if is_triple_choice():
		new_lines.columns = 3
		for choice in _roll.get("choices", []):
			if choice is Dictionary:
				new_lines.add_child(_choice_button(choice))
	else:
		new_lines.columns = 1
		new_title.text = "NEW  •  AURORA %d" % new_level
		for line in _roll.get("new_lines", []):
			if line is Dictionary:
				new_lines.add_child(_line_label(line_text(line), TIER_UP_COLOR if tier_up else NEW_COLOR))
	_refresh_actions()
	visible = true
	take_button.grab_focus()


func close() -> void:
	visible = false
	_roll = {}


func show_error(message: String) -> void:
	error_label.text = message
	set_busy(false)


func set_busy(value: bool) -> void:
	_busy = value
	_refresh_actions()


func must_take_new() -> bool:
	return bool(_roll.get("must_take_new", false))


func is_triple_choice() -> bool:
	return str(_roll.get("modifier_type", "")) == TRIPLE_CHOICE


func select_count() -> int:
	return int(_roll.get("select_count", 0))


## Picks or drops one of the triple choices (by its temp_id).
func toggle_choice(temp_id: int) -> void:
	if temp_id in _selected:
		_selected.erase(temp_id)
	elif _selected.size() < select_count():
		_selected.append(temp_id)
	for button in new_lines.get_children():
		if button is Button:
			button.set_pressed_no_signal(int(button.get_meta("temp_id")) in _selected)
	_refresh_actions()


static func _lines_text(count: int) -> String:
	return "%d line%s" % [count, "" if count == 1 else "s"]


static func line_text(line: Dictionary) -> String:
	var suffix := "%" if str(line.get("line_type", "flat")) == "percent" else ""
	var value := float(line.get("value", 0))
	var number := str(int(value)) if is_equal_approx(value, roundf(value)) else "%.1f" % value
	return "◆  %s  +%s%s" % [str(line.get("stat_type", "")).replace("_", " ").to_upper(), number, suffix]


func _refresh_actions() -> void:
	keep_button.disabled = _busy or must_take_new()
	keep_button.tooltip_text = "A tier-up roll must be taken." if must_take_new() else ""
	if is_triple_choice():
		new_title.text = "PICK %d  •  %d / %d SELECTED" % [select_count(), _selected.size(), select_count()]
		take_button.text = "APPLY SELECTED (%d/%d)" % [_selected.size(), select_count()]
		take_button.disabled = _busy or _selected.size() != select_count()
	else:
		take_button.text = "TAKE NEW LINES"
		take_button.disabled = _busy


func _on_take_pressed() -> void:
	if is_triple_choice():
		_decide("select_specific")
	else:
		_decide("take_new")


func _decide(action: String) -> void:
	if _busy or (action == "keep_old" and must_take_new()):
		return
	error_label.text = ""
	set_busy(true)
	decided.emit(action, _selected.duplicate())


func _choice_button(choice: Dictionary) -> Button:
	var button := Button.new()
	button.toggle_mode = true
	button.theme_type_variation = &"ChipButton"
	button.custom_minimum_size = Vector2(150, 40)
	button.text = line_text(choice)
	button.add_theme_font_size_override("font_size", 13)
	button.set_meta("temp_id", int(choice.get("temp_id", -1)))
	button.toggled.connect(func(_pressed): toggle_choice(int(choice.get("temp_id", -1))))
	return button


func _fill_lines(container: VBoxContainer, lines: Array, color: Color) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
	if lines.is_empty():
		container.add_child(_line_label("No lines", M3.ON_SURFACE_VARIANT))
	for line in lines:
		if line is Dictionary:
			container.add_child(_line_label(line_text(line), color))


static func _line_label(text: String, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", color)
	return label
