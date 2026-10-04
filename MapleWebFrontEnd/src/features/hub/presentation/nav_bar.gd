class_name NavBar
extends PanelContainer

## M3 navigation bar: 80dp on surfaceContainer. The active destination shows a
## 64×32dp secondaryContainer pill behind its icon, which grows in from the
## center when selected.

signal destination_selected(id: String)

const HEIGHT := 80.0

var _destinations: Dictionary = {}
var _selected := ""


func _init() -> void:
	custom_minimum_size = Vector2(0, HEIGHT)
	add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER, 0, 0.0))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 0)
	row.name = "Row"
	add_child(row)


## `entries`: [{"id", "label", "icon"}].
func setup(entries: Array) -> void:
	var row: HBoxContainer = get_node("Row")
	for entry in entries:
		var destination := Destination.new(str(entry.id), str(entry.label), str(entry.icon))
		destination.pressed.connect(_on_pressed.bind(destination.id))
		row.add_child(destination)
		_destinations[destination.id] = destination


func select(id: String, animate: bool = true) -> void:
	_selected = id
	for key in _destinations:
		_destinations[key].set_active(key == id, animate)


func selected() -> String:
	return _selected


func destination(id: String) -> Control:
	return _destinations.get(id)


func _on_pressed(id: String) -> void:
	destination_selected.emit(id)


class Destination:
	extends Button

	const PILL := Vector2(64, 32)

	var id := ""
	var _indicator := Panel.new()
	var _icon: Label
	var _label := Label.new()
	var _active := false
	var _tween: Tween

	func _init(destination_id: String, text_label: String, icon_name: String) -> void:
		id = destination_id
		name = destination_id.capitalize().replace(" ", "")
		size_flags_horizontal = Control.SIZE_EXPAND_FILL
		focus_mode = Control.FOCUS_NONE
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		tooltip_text = text_label
		set_meta("no_feedback", true)
		var empty := StyleBoxEmpty.new()
		for state in ["normal", "hover", "pressed", "hover_pressed", "focus", "disabled"]:
			add_theme_stylebox_override(state, empty)

		var column := VBoxContainer.new()
		column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		column.alignment = BoxContainer.ALIGNMENT_CENTER
		column.add_theme_constant_override("separation", 4)
		column.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(column)
		var pill_host := Control.new()
		pill_host.custom_minimum_size = PILL
		pill_host.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		pill_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
		column.add_child(pill_host)
		_indicator.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_indicator.size = PILL
		_indicator.pivot_offset = PILL / 2.0
		_indicator.add_theme_stylebox_override("panel", M3.box(M3.SECONDARY_CONTAINER, M3.CORNER_FULL, 0.0))
		_indicator.scale = Vector2(0.0, 1.0)
		pill_host.add_child(_indicator)
		_icon = M3.icon_label(icon_name, 24)
		_icon.size = PILL
		pill_host.add_child(_icon)
		_label.text = text_label
		_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_label.add_theme_font_size_override("font_size", M3.LABEL_MEDIUM)
		_label.add_theme_font_override("font", M3.FONT_MEDIUM)
		_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		column.add_child(_label)
		UiFeedback.attach(self, M3.ON_SURFACE)
		mouse_entered.connect(_refresh_hover.bind(true))
		mouse_exited.connect(_refresh_hover.bind(false))
		_paint()

	func set_active(value: bool, animate: bool) -> void:
		_active = value
		if _tween:
			_tween.kill()
		var target := Vector2.ONE if value else Vector2(0.0, 1.0)
		if animate and is_inside_tree():
			_tween = create_tween()
			M3.ease_tween(_tween).tween_property(_indicator, "scale", target, M3.DURATION_MEDIUM)
		else:
			_indicator.scale = target
		_paint()

	func _refresh_hover(hovered: bool) -> void:
		if not _active:
			var layer := M3.with_alpha(M3.ON_SURFACE, M3.HOVER_OPACITY) if hovered else Color.TRANSPARENT
			_indicator.add_theme_stylebox_override("panel", M3.box(layer, M3.CORNER_FULL, 0.0))
			_indicator.scale = Vector2.ONE if hovered else Vector2(0.0, 1.0)
		else:
			var color := M3.layered(M3.SECONDARY_CONTAINER, M3.ON_SECONDARY_CONTAINER, M3.HOVER_OPACITY) if hovered else M3.SECONDARY_CONTAINER
			_indicator.add_theme_stylebox_override("panel", M3.box(color, M3.CORNER_FULL, 0.0))

	func _paint() -> void:
		if _active:
			_indicator.add_theme_stylebox_override("panel", M3.box(M3.SECONDARY_CONTAINER, M3.CORNER_FULL, 0.0))
		_icon.add_theme_color_override("font_color", M3.ON_SECONDARY_CONTAINER if _active else M3.ON_SURFACE_VARIANT)
		_label.add_theme_color_override("font_color", M3.ON_SURFACE if _active else M3.ON_SURFACE_VARIANT)
		_label.add_theme_font_override("font", M3.FONT_BOLD if _active else M3.FONT_MEDIUM)
