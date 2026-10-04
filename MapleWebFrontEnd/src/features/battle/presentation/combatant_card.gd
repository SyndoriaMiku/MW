class_name CombatantCard
extends PanelContainer

## One combatant on the battle field: name, placeholder portrait, HP/MP bars and
## active effects. Enemy cards are clicked to pick the attack target.

signal pressed(combatant_id: int)

const PLAYER_PORTRAIT := M3.PRIMARY_CONTAINER
const ENEMY_PORTRAIT := M3.ERROR_CONTAINER
const SELECTED_BORDER := M3.TERTIARY
const TURN_BORDER := M3.PRIMARY
const BASE_BORDER := M3.OUTLINE_VARIANT

var combatant_id := 0
var _base_border := BASE_BORDER
var _style := StyleBoxFlat.new()
var _name_label := Label.new()
var _badge_label := Label.new()
var _portrait := ColorRect.new()
var _portrait_label := Label.new()
var _hp_bar := ProgressBar.new()
var _hp_label := Label.new()
var _mp_bar := ProgressBar.new()
var _mp_label := Label.new()
var _effects_label := Label.new()
var _shown_hp := 0
var _shown_mp := 0
var _max_hp := 1
var _max_mp := 1


func _init(is_player: bool) -> void:
	custom_minimum_size = Vector2(0, 168 if is_player else 196)
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_ARROW if is_player else Control.CURSOR_POINTING_HAND
	_style = M3.box(M3.SURFACE_CONTAINER_LOWEST, M3.CORNER_CARD, 12.0, BASE_BORDER, 2)
	add_theme_stylebox_override("panel", _style)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 5)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)

	var header := HBoxContainer.new()
	header.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(header)
	_name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	_name_label.add_theme_font_size_override("font_size", 17)
	header.add_child(_name_label)
	_badge_label.add_theme_font_size_override("font_size", 11)
	_badge_label.add_theme_color_override("font_color", TURN_BORDER)
	header.add_child(_badge_label)

	_portrait.custom_minimum_size = Vector2(0, 52 if is_player else 84)
	_portrait.color = PLAYER_PORTRAIT if is_player else ENEMY_PORTRAIT
	_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(_portrait)
	_portrait_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_portrait_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_portrait_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_portrait_label.add_theme_font_size_override("font_size", 20)
	_portrait_label.add_theme_color_override("font_color", M3.ON_PRIMARY_CONTAINER if is_player else M3.ON_ERROR_CONTAINER)
	_portrait.add_child(_portrait_label)

	box.add_child(_bar_row(_hp_bar, _hp_label, &"HPBar" if is_player else &"EnemyHPBar"))
	if is_player:
		box.add_child(_bar_row(_mp_bar, _mp_label, &"MPBar"))
	_effects_label.add_theme_font_size_override("font_size", 11)
	_effects_label.add_theme_color_override("font_color", M3.EPIC)
	_effects_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	box.add_child(_effects_label)


func bind(combatant: CombatantState, is_local: bool, has_turn: bool) -> void:
	combatant_id = combatant.id
	_name_label.text = combatant.display_name + ("  (YOU)" if is_local else "")
	_portrait_label.text = combatant.display_name.to_upper()
	_badge_label.text = "LEFT" if combatant.has_left else ("TURN" if has_turn else "")
	_max_hp = combatant.max_hp
	_max_mp = combatant.max_mp
	_set_hp(combatant.current_hp, false)
	_set_mp(combatant.current_mp, false)
	var effects := combatant.effect_names()
	_effects_label.text = "  ".join(effects)
	_effects_label.tooltip_text = "\n".join(effects)
	modulate.a = 1.0 if combatant.is_alive() else M3.DISABLED_CONTENT_OPACITY
	_base_border = TURN_BORDER if has_turn else BASE_BORDER
	_style.border_color = _base_border


## Grows the card (and its portrait) to fill the space the field gives it.
func set_card_height(height: float) -> void:
	var extra := height - custom_minimum_size.y
	custom_minimum_size.y = height
	_portrait.custom_minimum_size.y = maxf(40.0, _portrait.custom_minimum_size.y + extra)


func set_selected(selected: bool) -> void:
	_style.border_color = SELECTED_BORDER if selected else _base_border


## Shows a hit before the server snapshot is applied: moves the bar and flashes.
func apply_hit(kind: String, amount: int) -> void:
	match kind:
		"damage":
			_set_hp(_shown_hp - amount, true)
			_flash(Color(1.6, 0.6, 0.6))
		"heal":
			_set_hp(_shown_hp + amount, true)
			_flash(Color(0.7, 1.5, 0.8))
		"mp":
			_set_mp(_shown_mp + amount, true)
		"blocked":
			_flash(Color(1.3, 1.3, 1.6))


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		pressed.emit(combatant_id)
		accept_event()


func _set_hp(value: int, animate: bool) -> void:
	_shown_hp = clampi(value, 0, _max_hp)
	_hp_label.text = "HP  %d / %d" % [_shown_hp, _max_hp]
	_move_bar(_hp_bar, _max_hp, _shown_hp, animate)


func _set_mp(value: int, animate: bool) -> void:
	_shown_mp = clampi(value, 0, _max_mp)
	_mp_label.text = "MP  %d / %d" % [_shown_mp, _max_mp]
	_move_bar(_mp_bar, _max_mp, _shown_mp, animate)


func _move_bar(bar: ProgressBar, max_value: int, value: int, animate: bool) -> void:
	bar.max_value = max_value
	if animate and is_inside_tree():
		create_tween().tween_property(bar, "value", float(value), 0.25)
	else:
		bar.value = value


func _flash(color: Color) -> void:
	if not is_inside_tree():
		return
	_portrait.pivot_offset = _portrait.size / 2.0
	var tween := create_tween()
	tween.tween_property(_portrait, "modulate", color, 0.06)
	tween.parallel().tween_property(_portrait, "scale", Vector2(1.06, 1.06), 0.06)
	tween.tween_property(_portrait, "modulate", Color.WHITE, 0.2)
	tween.parallel().tween_property(_portrait, "scale", Vector2.ONE, 0.2)


static func _bar_row(bar: ProgressBar, label: Label, variation: StringName) -> Control:
	var row := VBoxContainer.new()
	row.add_theme_constant_override("separation", 2)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", 12)
	row.add_child(label)
	bar.theme_type_variation = variation
	bar.custom_minimum_size = Vector2(0, 12)
	bar.show_percentage = false
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(bar)
	return row
