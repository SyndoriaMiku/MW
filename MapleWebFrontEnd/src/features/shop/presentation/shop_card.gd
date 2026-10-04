class_name ShopCard
extends PanelContainer

## A clickable item tile: a click selects it, a double click activates it
## (buy, sell or buy back, depending on where it is shown).

signal selected(card: ShopCard)
signal activated(card: ShopCard)


## The shop item, inventory item or sold item this card shows.
var data: Dictionary = {}
var _style := StyleBoxFlat.new()


## `compact` makes a one-line row (bag); otherwise a tile with a large icon.
func _init(icon: Texture2D, title: String, lines: PackedStringArray, compact: bool, dimmed: bool) -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	custom_minimum_size = Vector2(0, 54) if compact else Vector2(156, 176)
	_style = M3.box(M3.SURFACE_CONTAINER_LOWEST, M3.CORNER_MEDIUM, 8.0)
	add_theme_stylebox_override("panel", _style)
	modulate.a = 0.5 if dimmed else 1.0
	UiFeedback.attach(self, M3.ON_SURFACE)

	var box: BoxContainer = HBoxContainer.new() if compact else VBoxContainer.new()
	box.add_theme_constant_override("separation", 8 if compact else 3)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)
	var icon_rect := TextureRect.new()
	icon_rect.texture = icon
	icon_rect.custom_minimum_size = Vector2(40, 40) if compact else Vector2(0, 84)
	icon_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon_rect.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	icon_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(icon_rect)
	if icon == null:
		var initials := Label.new()
		initials.text = _initials(title)
		initials.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		initials.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		initials.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		initials.add_theme_color_override("font_color", M3.ON_SURFACE_VARIANT)
		icon_rect.add_child(initials)

	var text_box := VBoxContainer.new()
	text_box.add_theme_constant_override("separation", 0)
	text_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text_box.alignment = BoxContainer.ALIGNMENT_CENTER
	text_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(text_box)
	var title_label := Label.new()
	title_label.text = title
	title_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT if compact else HORIZONTAL_ALIGNMENT_CENTER
	title_label.add_theme_font_size_override("font_size", 14 if compact else 13)
	text_box.add_child(title_label)
	for index in lines.size():
		var line := Label.new()
		line.text = lines[index]
		line.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		line.horizontal_alignment = title_label.horizontal_alignment
		line.add_theme_font_size_override("font_size", 11)
		line.add_theme_color_override("font_color", M3.GOLD if index == 0 else M3.ON_SURFACE_VARIANT)
		text_box.add_child(line)


func set_selected(value: bool) -> void:
	_style.bg_color = M3.SECONDARY_CONTAINER if value else M3.SURFACE_CONTAINER_LOWEST
	_style.border_color = M3.PRIMARY
	_style.set_border_width_all(2 if value else 0)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		accept_event()
		if event.double_click:
			activated.emit(self)
		else:
			selected.emit(self)


static func _initials(title: String) -> String:
	var result := ""
	for word in title.split(" ", false):
		result += word.left(1).to_upper()
	return result.left(3)
