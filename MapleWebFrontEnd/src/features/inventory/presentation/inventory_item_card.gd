class_name InventoryItemCard
extends PanelContainer

## One inventory slot. Click selects, double click acts on the item (equip,
## use, open enhancement), middle click cycles the compared slot, and hovering
## reports the mouse so the screen can show its tooltip.

signal selected(card: InventoryItemCard)
signal activated(card: InventoryItemCard)
signal compare_cycled(card: InventoryItemCard)
signal hover_started(card: InventoryItemCard)
signal hover_moved(card: InventoryItemCard)
signal hover_ended(card: InventoryItemCard)

var item: Dictionary = {}


func _init(inventory_item: Dictionary, is_selected: bool, is_equipped: bool) -> void:
	item = inventory_item
	var template: Dictionary = item.get("template", {})
	custom_minimum_size = Vector2(112, 132)
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var style := StyleBoxFlat.new()
	style.bg_color = Color("101a29")
	style.border_color = Color("53d985") if is_selected else (Color("42a7d6") if is_equipped else Color("2d435e"))
	style.set_border_width_all(2 if is_selected or is_equipped else 1)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(7)
	add_theme_stylebox_override("panel", style)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)
	var icon_host := Control.new()
	icon_host.custom_minimum_size = Vector2(0, 82)
	icon_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(icon_host)
	var texture := ItemIcons.for_template(template)
	if texture != null:
		var icon := TextureRect.new()
		icon.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 8)
		icon.texture = texture
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon_host.add_child(icon)
	else:
		var placeholder := Label.new()
		placeholder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		placeholder.text = _initials(str(template.get("name", "?")))
		placeholder.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		placeholder.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		placeholder.add_theme_color_override("font_color", Color("607089"))
		placeholder.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon_host.add_child(placeholder)

	var name_label := Label.new()
	name_label.text = str(template.get("name", "Unknown Item"))
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name_label.add_theme_font_size_override("font_size", 12)
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(name_label)
	var meta_label := Label.new()
	meta_label.text = "EQUIPPED" if is_equipped else "x%d" % int(item.get("quantity", 1))
	meta_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	meta_label.add_theme_font_size_override("font_size", 10)
	meta_label.add_theme_color_override("font_color", Color("53d985") if is_equipped else Color("8295aa"))
	meta_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(meta_label)

	mouse_entered.connect(func(): hover_started.emit(self))
	mouse_exited.connect(func(): hover_ended.emit(self))


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		hover_moved.emit(self)
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			accept_event()
			if event.double_click:
				activated.emit(self)
			else:
				selected.emit(self)
		elif event.button_index == MOUSE_BUTTON_MIDDLE:
			accept_event()
			compare_cycled.emit(self)


static func _initials(item_name: String) -> String:
	var initials := ""
	for word in item_name.split(" ", false):
		initials += word.left(1).to_upper()
	return initials.left(3)
