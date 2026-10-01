extends Control

@onready var back_button: Button = %BackButton
@onready var refresh_button: Button = %RefreshButton
@onready var enhancement_button: Button = %EnhancementButton
@onready var search_input: LineEdit = %SearchInput
@onready var category_filter: OptionButton = %CategoryFilter
@onready var item_count: Label = %ItemCount
@onready var item_grid: GridContainer = %ItemGrid
@onready var empty_label: Label = %EmptyLabel
@onready var detail_name: Label = %DetailName
@onready var detail_type: Label = %DetailType
@onready var detail_icon: TextureRect = %DetailIcon
@onready var detail_state: Label = %DetailState
@onready var detail_stats: Label = %DetailStats
@onready var detail_description: Label = %DetailDescription
@onready var action_button: Button = %ActionButton
@onready var status_label: Label = %StatusLabel

var _items: Array = []
var _equipped_item_ids: Dictionary = {}
var _equipped_slot_indices_by_type: Dictionary = {}
var _selected_item: Dictionary = {}
var _is_loading := false


func _ready() -> void:
	back_button.pressed.connect(_on_back_pressed)
	refresh_button.pressed.connect(_load_inventory)
	enhancement_button.pressed.connect(_on_enhancement_pressed)
	search_input.text_changed.connect(_on_filter_changed)
	category_filter.item_selected.connect(_on_category_changed)
	action_button.pressed.connect(_on_action_pressed)
	_setup_categories()
	if not SceneRouter.require_session():
		return
	await _load_inventory()


func _setup_categories() -> void:
	for entry in [
		{"label": "All items", "value": "all"},
		{"label": "Equipment", "value": "equipment"},
		{"label": "Consumables", "value": "use"},
		{"label": "Materials", "value": "etc"},
	]:
		category_filter.add_item(entry.label)
		category_filter.set_item_metadata(category_filter.item_count - 1, entry.value)


func _load_inventory() -> void:
	if _is_loading:
		return
	_set_loading(true, "Loading inventory...")
	var selected_id := ApiClient.id_string(_selected_item.get("id"))
	var inventory_response: Dictionary = await ApiClient.get_json("inventory/")
	if not _accept_response(inventory_response):
		return
	_items = ApiClient.unwrap_list(inventory_response.get("data", []))

	var equipped_response: Dictionary = await ApiClient.get_json("inventory/equipped/")
	if not _accept_response(equipped_response):
		return
	_equipped_item_ids.clear()
	_equipped_slot_indices_by_type.clear()
	for equipped in ApiClient.unwrap_list(equipped_response.get("data", [])):
		var equipped_item: Dictionary = equipped.get("item", {})
		_equipped_item_ids[ApiClient.id_string(equipped_item.get("id"))] = true
		var equipped_type := str(equipped_item.get("template", {}).get("item_type", ""))
		if not _equipped_slot_indices_by_type.has(equipped_type):
			_equipped_slot_indices_by_type[equipped_type] = {}
		var type_slots: Dictionary = _equipped_slot_indices_by_type[equipped_type]
		type_slots[int(equipped.get("slot_index", 0))] = true

	_selected_item = _find_item_by_id(selected_id)
	if _selected_item.is_empty() and not _items.is_empty():
		_selected_item = _items[0]
	_render_inventory()
	_render_details()
	_set_loading(false, "Inventory synchronized with the server.")


func _render_inventory() -> void:
	_clear_children(item_grid)
	var visible_items := _filtered_items()
	item_count.text = "%d ITEM%s" % [_items.size(), "" if _items.size() == 1 else "S"]
	empty_label.visible = visible_items.is_empty()
	for item in visible_items:
		item_grid.add_child(_create_item_card(item))


func _create_item_card(item: Dictionary) -> Control:
	var template: Dictionary = item.get("template", {})
	var item_id := ApiClient.id_string(item.get("id"))
	var is_selected := item_id == ApiClient.id_string(_selected_item.get("id"))
	var is_equipped := _equipped_item_ids.has(item_id)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(112, 132)
	card.tooltip_text = str(template.get("name", "Unknown Item"))
	var style := StyleBoxFlat.new()
	style.bg_color = Color("101a29")
	style.border_color = Color("53d985") if is_selected else (Color("42a7d6") if is_equipped else Color("2d435e"))
	style.set_border_width_all(2 if is_selected or is_equipped else 1)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(7)
	card.add_theme_stylebox_override("panel", style)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	card.add_child(box)
	var icon_host := Control.new()
	icon_host.custom_minimum_size = Vector2(0, 82)
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
		placeholder.text = _item_initials(str(template.get("name", "?")))
		placeholder.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		placeholder.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		placeholder.add_theme_color_override("font_color", Color("607089"))
		placeholder.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon_host.add_child(placeholder)

	var click_target := Button.new()
	click_target.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	click_target.flat = true
	click_target.tooltip_text = card.tooltip_text
	click_target.pressed.connect(_on_item_selected.bind(item))
	icon_host.add_child(click_target)

	var name_label := Label.new()
	name_label.text = str(template.get("name", "Unknown Item"))
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name_label.add_theme_font_size_override("font_size", 12)
	box.add_child(name_label)
	var meta_label := Label.new()
	meta_label.text = "EQUIPPED" if is_equipped else "x%d" % int(item.get("quantity", 1))
	meta_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	meta_label.add_theme_font_size_override("font_size", 10)
	meta_label.add_theme_color_override("font_color", Color("53d985") if is_equipped else Color("8295aa"))
	box.add_child(meta_label)
	return card


func _render_details() -> void:
	if _selected_item.is_empty():
		detail_name.text = "Select an item"
		detail_type.text = "—"
		detail_icon.texture = null
		detail_state.text = ""
		detail_stats.text = "Choose an inventory slot to inspect its stats."
		detail_description.text = ""
		action_button.text = "SELECT AN ITEM"
		action_button.disabled = true
		return

	var template: Dictionary = _selected_item.get("template", {})
	var item_type := str(template.get("item_type", "etc"))
	var is_equipment := ItemTypes.is_equipment(item_type)
	var is_equipped := _equipped_item_ids.has(ApiClient.id_string(_selected_item.get("id")))
	detail_name.text = str(template.get("name", "Unknown Item"))
	detail_type.text = "%s  •  Required level %d" % [item_type.replace("_", " ").capitalize(), int(template.get("minimum_level", 1))]
	detail_icon.texture = ItemIcons.for_template(template)
	detail_state.text = _item_state_text(_selected_item, is_equipped)
	detail_stats.text = _item_stats_text(_selected_item)
	detail_description.text = str(template.get("description", "No description available."))
	if is_equipment:
		action_button.text = "UNEQUIP" if is_equipped else "EQUIP"
		action_button.disabled = bool(_selected_item.get("is_destroyed", false)) or _is_loading
	else:
		action_button.text = "NO ACTION AVAILABLE"
		action_button.disabled = true


func _item_state_text(item: Dictionary, is_equipped: bool) -> String:
	var parts := PackedStringArray()
	parts.append("Equipped" if is_equipped else "In inventory")
	parts.append("Quantity %d" % int(item.get("quantity", 1)))
	var lumen := int(item.get("lumen_ascend_level", 0))
	var aurora := int(item.get("aurora_level", 0))
	if lumen > 0:
		parts.append("Lumen +%d" % lumen)
	if aurora > 0:
		parts.append("Aurora +%d" % aurora)
	if bool(item.get("is_destroyed", false)):
		parts.append("Destroyed")
	return "  •  ".join(parts)


func _item_stats_text(item: Dictionary) -> String:
	var template: Dictionary = item.get("template", {})
	var lines := PackedStringArray()
	for stat in ["hp", "mp", "att", "str", "agi", "int", "all_stats"]:
		var value := int(template.get("%s_boost" % stat, 0))
		if value != 0:
			lines.append("%s  %+d" % [stat.replace("_", " ").to_upper(), value])
	var drop_rate := float(template.get("drop_rate_boost", 0.0))
	if drop_rate != 0.0:
		lines.append("DROP RATE  +%.1f%%" % drop_rate)
	for line in item.get("aurora_lines", []):
		var suffix := "%" if str(line.get("line_type", "flat")) == "percent" else ""
		lines.append("AURORA  %s +%s%s" % [str(line.get("stat_type", "")).to_upper(), str(line.get("value", 0)), suffix])
	if lines.is_empty():
		lines.append("No combat stat bonuses")
	return "\n".join(lines)


func _filtered_items() -> Array:
	var results: Array = []
	var query := search_input.text.strip_edges().to_lower()
	var category := "all"
	if category_filter.selected >= 0:
		category = str(category_filter.get_item_metadata(category_filter.selected))
	for item in _items:
		var template: Dictionary = item.get("template", {})
		var name := str(template.get("name", "")).to_lower()
		var item_type := str(template.get("item_type", "etc"))
		var category_matches := category == "all" or item_type == category or (category == "equipment" and ItemTypes.is_equipment(item_type))
		if category_matches and (query.is_empty() or name.contains(query)):
			results.append(item)
	return results


func _on_item_selected(item: Dictionary) -> void:
	_selected_item = item
	_render_inventory()
	_render_details()


func _on_action_pressed() -> void:
	if _selected_item.is_empty() or _is_loading:
		return
	var item_id := ApiClient.id_string(_selected_item.get("id"))
	var is_equipped := _equipped_item_ids.has(item_id)
	_set_loading(true, "Updating equipment...")
	var response: Dictionary
	if is_equipped:
		response = await ApiClient.post_json("inventory/%s/unequip/" % item_id)
	else:
		var item_type := str(_selected_item.get("template", {}).get("item_type", ""))
		response = await ApiClient.post_json(
			"inventory/%s/equip/" % item_id,
			{"slot_index": _next_available_slot_index(item_type)}
		)
	if not _accept_response(response):
		return
	var action_message := str(response.get("data", {}).get(
		"status",
		"Item unequipped." if is_equipped else "Item equipped."
	))
	_apply_equipment_response(response.get("data", {}), item_id, is_equipped)
	_render_inventory()
	_render_details()
	await _load_inventory_after_action()
	status_label.text = action_message


func _next_available_slot_index(item_type: String) -> int:
	var max_slots := 1
	if item_type == "ring":
		max_slots = 4
	elif item_type == "pendant":
		max_slots = 2
	var used: Dictionary = _equipped_slot_indices_by_type.get(item_type, {})
	for index in range(max_slots):
		if not used.has(index):
			return index
	return 0


func _apply_equipment_response(payload: Dictionary, item_id: String, was_equipped: bool) -> void:
	if was_equipped:
		_equipped_item_ids.erase(item_id)
		var returned_item: Variant = payload.get("item", {})
		if returned_item is Dictionary and not returned_item.is_empty():
			_selected_item = returned_item
		return
	var replaced_item_id := ApiClient.id_string(payload.get("replaced_item_id"))
	if not replaced_item_id.is_empty():
		_equipped_item_ids.erase(replaced_item_id)
	_equipped_item_ids[item_id] = true
	var equipped: Variant = payload.get("equipped", {})
	if equipped is Dictionary:
		var returned_item: Variant = equipped.get("item", {})
		if returned_item is Dictionary and not returned_item.is_empty():
			_selected_item = returned_item


func _load_inventory_after_action() -> void:
	_is_loading = false
	await _load_inventory()


func _on_filter_changed(_value: String) -> void:
	_render_inventory()


func _on_category_changed(_index: int) -> void:
	_render_inventory()


func _find_item_by_id(item_id: String) -> Dictionary:
	if item_id.is_empty():
		return {}
	for item in _items:
		if ApiClient.id_string(item.get("id")) == item_id:
			return item
	return {}


func _item_initials(item_name: String) -> String:
	var initials := ""
	for word in item_name.split(" ", false):
		initials += word.left(1).to_upper()
	return initials.left(3)


func _accept_response(response: Dictionary) -> bool:
	if response.get("ok", false):
		return true
	_set_loading(false, ApiClient.error_message(response, "Unable to load inventory."))
	return false


func _set_loading(is_loading: bool, message: String) -> void:
	_is_loading = is_loading
	refresh_button.disabled = is_loading
	back_button.disabled = is_loading
	enhancement_button.disabled = is_loading
	search_input.editable = not is_loading
	category_filter.disabled = is_loading
	status_label.text = message
	_render_details()


func _clear_children(parent: Node) -> void:
	for child in parent.get_children():
		child.queue_free()


func _on_back_pressed() -> void:
	SceneRouter.go_to(SceneRouter.LAUNCHER)


func _on_enhancement_pressed() -> void:
	SceneRouter.go_to(SceneRouter.ENHANCEMENT)
