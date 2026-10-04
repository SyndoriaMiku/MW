extends Control

## Inventory. Double click (or the action button) equips/unequips equipment,
## uses buff items and opens enhancement for essences. Hovering shows the item;
## equipment is compared with the equipped item in the same slot, and a middle
## click cycles through the equipped copies of multi-slot items (rings, pendants).

## Used when the backend's slot configuration cannot be loaded.
const DEFAULT_SLOT_CAPACITY := {"ring": 4, "pendant": 2}

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
var _equipped: Array = []
var _equipped_item_ids: Dictionary = {}
var _slot_capacity: Dictionary = DEFAULT_SLOT_CAPACITY.duplicate()
var _selected_item: Dictionary = {}
var _hovered_item: Dictionary = {}
var _compare_index := 0
var _is_loading := false
var _tooltip := ItemHoverTooltip.new()


func _ready() -> void:
	HubEmbed.adapt(self, [back_button], $Margin)
	if HubEmbed.is_embedded(self):
		%IconPanel.custom_minimum_size.y = 120
	add_child(_tooltip)
	back_button.pressed.connect(_on_back_pressed)
	refresh_button.pressed.connect(func():
		GameCache.clear_all()
		_load_inventory()
	)
	enhancement_button.pressed.connect(_on_enhancement_pressed)
	search_input.text_changed.connect(_on_filter_changed)
	category_filter.item_selected.connect(_on_category_changed)
	action_button.pressed.connect(func(): _activate(_selected_item))
	_setup_categories()
	if not SceneRouter.require_session():
		return
	await _load_slot_capacity()
	await _load_inventory()


## Called by the hub each time this page is shown again.
func reload_page() -> void:
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


## How many of each item type can be worn at once, from the backend's slots.
func _load_slot_capacity() -> void:
	var response: Dictionary = await GameCache.get_all("inventory/slots/")
	if not response.get("ok", false):
		return
	var capacity := {}
	for slot in response.data:
		for item_type in slot.get("allowed_item_types", []):
			capacity[str(item_type)] = int(slot.get("max_count", 1))
	if not capacity.is_empty():
		_slot_capacity = capacity


func _load_inventory() -> void:
	if _is_loading:
		return
	_set_loading(true, "Loading inventory...")
	var selected_id := ApiClient.id_string(_selected_item.get("id"))
	var inventory_response: Dictionary = await GameCache.get_all("inventory/")
	if not _accept_response(inventory_response):
		return
	var equipped_response: Dictionary = await GameCache.get_all("inventory/equipped/")
	if not _accept_response(equipped_response):
		return
	_items = inventory_response.data
	set_equipped(equipped_response.data)
	_selected_item = _find_item_by_id(selected_id)
	if _selected_item.is_empty() and not _items.is_empty():
		_selected_item = _items[0]
	_render_inventory()
	_render_details()
	_set_loading(false, "Inventory synchronized. Double-click an item to equip or use it; hover to compare.")


func set_equipped(entries: Array) -> void:
	_equipped = entries.filter(func(entry): return entry is Dictionary)
	_equipped.sort_custom(func(a, b): return int(a.get("slot_index", 0)) < int(b.get("slot_index", 0)))
	_equipped_item_ids.clear()
	for entry in _equipped:
		_equipped_item_ids[ApiClient.id_string(entry.get("item", {}).get("id"))] = true


## Equipped entries ({slot, slot_index, item}) holding this item type, by slot index.
func equipped_for_type(item_type: String) -> Array:
	return _equipped.filter(func(entry): return str(entry.get("item", {}).get("template", {}).get("item_type", "")) == item_type)


func capacity_for(item_type: String) -> int:
	return int(_slot_capacity.get(item_type, 1))


## Where equipping goes: the first free slot, otherwise the slot being compared.
func target_slot_index(item_type: String, compare_index: int) -> int:
	var worn := equipped_for_type(item_type)
	var used := {}
	for entry in worn:
		used[int(entry.get("slot_index", 0))] = true
	for index in capacity_for(item_type):
		if not used.has(index):
			return index
	if worn.is_empty():
		return 0
	return int(worn[posmod(compare_index, worn.size())].get("slot_index", 0))


## What a double click does with this item: {"kind", "label"}.
func item_action(item: Dictionary) -> Dictionary:
	var template: Dictionary = item.get("template", {})
	if ItemTypes.is_equipment(str(template.get("item_type", ""))):
		if _equipped_item_ids.has(ApiClient.id_string(item.get("id"))):
			return {"kind": "unequip", "label": "UNEQUIP"}
		if bool(item.get("is_destroyed", false)):
			return {"kind": "none", "label": "DESTROYED"}
		return {"kind": "equip", "label": "EQUIP"}
	match str(template.get("use_kind", "")):
		"aurora_modifier":
			return {"kind": "aurora", "label": "USE ON EQUIPMENT (AURORA)"}
		"lumen_modifier":
			return {"kind": "lumen", "label": "OPEN LUMEN ENHANCEMENT"}
		"timed_buff":
			return {"kind": "use", "label": "USE"}
		"battle":
			return {"kind": "battle", "label": "USE IN BATTLE"}
		"fragment_restore":
			return {"kind": "restore", "label": "RESTORES DESTROYED ITEMS"}
	return {"kind": "none", "label": "NO ACTION"}


func _activate(item: Dictionary) -> void:
	if item.is_empty() or _is_loading:
		return
	var item_id := ApiClient.id_string(item.get("id"))
	var template: Dictionary = item.get("template", {})
	match str(item_action(item).kind):
		"equip":
			var item_type := str(template.get("item_type", ""))
			var compare := _compare_index if ApiClient.id_string(_hovered_item.get("id")) == item_id else 0
			await _change_equipment("inventory/%s/equip/" % item_id, {"slot_index": target_slot_index(item_type, compare)}, "Equipping...")
		"unequip":
			await _change_equipment("inventory/%s/unequip/" % item_id, {}, "Unequipping...")
		"aurora":
			SceneRouter.go_to(SceneRouter.ENHANCEMENT, {"tab": "aurora", "essence_id": item_id})
		"lumen":
			SceneRouter.go_to(SceneRouter.ENHANCEMENT, {"tab": "lumen"})
		"use":
			await _use_item(item)
		"battle":
			status_label.text = "Use %s during a battle with the ITEM button." % str(template.get("name", "this item"))
		"restore":
			status_label.text = "%s restores a destroyed item; restoring is not in the client yet." % str(template.get("name", "This item"))
		_:
			status_label.text = "%s has no direct use; it is a material for enhancement and crafting." % str(template.get("name", "This item"))


func _change_equipment(path: String, payload: Dictionary, message: String) -> void:
	_tooltip.hide_tooltip()
	_set_loading(true, message)
	var response: Dictionary = await ApiClient.post_json(path, payload)
	if not _accept_response(response):
		return
	var result := str(response.data.get("status", "Equipment updated."))
	_is_loading = false
	await _load_inventory()
	status_label.text = result


func _use_item(item: Dictionary) -> void:
	_tooltip.hide_tooltip()
	_set_loading(true, "Using %s..." % str(item.get("template", {}).get("name", "item")))
	var response: Dictionary = await ApiClient.post_json("inventory/%s/use/" % ApiClient.id_string(item.get("id")))
	if not _accept_response(response):
		return
	_is_loading = false
	await _load_inventory()
	status_label.text = str(response.data.get("status", "Item used."))


func _render_inventory() -> void:
	for child in item_grid.get_children():
		item_grid.remove_child(child)
		child.queue_free()
	var visible_items := _filtered_items()
	item_count.text = "%d ITEM%s" % [_items.size(), "" if _items.size() == 1 else "S"]
	empty_label.visible = visible_items.is_empty()
	for item in visible_items:
		item_grid.add_child(_create_item_card(item))


func _create_item_card(item: Dictionary) -> InventoryItemCard:
	var item_id := ApiClient.id_string(item.get("id"))
	var card := InventoryItemCard.new(item, item_id == ApiClient.id_string(_selected_item.get("id")), _equipped_item_ids.has(item_id))
	card.selected.connect(func(clicked: InventoryItemCard): _on_item_selected(clicked.item))
	card.activated.connect(func(clicked: InventoryItemCard): _activate(clicked.item))
	card.compare_cycled.connect(func(clicked: InventoryItemCard): _cycle_compare(clicked.item))
	card.hover_started.connect(func(hovered: InventoryItemCard): _on_hover_started(hovered.item))
	card.hover_moved.connect(func(_hovered): _tooltip.follow(get_global_mouse_position()))
	card.hover_ended.connect(func(hovered: InventoryItemCard): _on_hover_ended(hovered.item))
	return card


func _on_hover_started(item: Dictionary) -> void:
	if ApiClient.id_string(item.get("id")) != ApiClient.id_string(_hovered_item.get("id")):
		_compare_index = 0
	_hovered_item = item
	_show_tooltip()


func _on_hover_ended(item: Dictionary) -> void:
	if ApiClient.id_string(item.get("id")) == ApiClient.id_string(_hovered_item.get("id")):
		_hovered_item = {}
		_tooltip.hide_tooltip()


## Middle click on a ring or pendant: compare with the next equipped copy.
func _cycle_compare(item: Dictionary) -> void:
	_hovered_item = item
	var worn := equipped_for_type(str(item.get("template", {}).get("item_type", "")))
	if worn.size() > 1:
		_compare_index = posmod(_compare_index + 1, worn.size())
	_show_tooltip()


## The equipped entry the hovered item is compared with, or {}.
func compare_entry(item: Dictionary) -> Dictionary:
	var worn := equipped_for_type(str(item.get("template", {}).get("item_type", "")))
	if worn.is_empty() or _equipped_item_ids.has(ApiClient.id_string(item.get("id"))):
		return {}
	return worn[posmod(_compare_index, worn.size())]


func _show_tooltip() -> void:
	if _hovered_item.is_empty():
		_tooltip.hide_tooltip()
		return
	var template: Dictionary = _hovered_item.get("template", {})
	var item_type := str(template.get("item_type", ""))
	var action := item_action(_hovered_item)
	var hint := "Double-click: %s" % str(action.label).to_lower() if action.kind != "none" else ""
	if not ItemTypes.is_equipment(item_type):
		_tooltip.show_simple(_hovered_item, hint)
	elif _equipped_item_ids.has(ApiClient.id_string(_hovered_item.get("id"))):
		_tooltip.show_equipment(_hovered_item, {}, "", "", {}, _equipped, hint)
	else:
		var worn := equipped_for_type(item_type)
		var entry := compare_entry(_hovered_item)
		var capacity := capacity_for(item_type)
		var slot_name := item_type.replace("_", " ")
		var caption := slot_name.to_upper()
		if capacity > 1 and not entry.is_empty():
			caption = "%s %d / %d" % [slot_name.to_upper(), int(entry.get("slot_index", 0)) + 1, capacity]
		if worn.size() > 1:
			hint += "\nMiddle-click: compare with the next equipped %s (%d/%d)" % [slot_name, posmod(_compare_index, worn.size()) + 1, worn.size()]
		# Say what a double click really does: fill a free slot or replace the compared one.
		var target := target_slot_index(item_type, _compare_index)
		var replaced := {}
		var outcome := "goes into the empty %s slot" % slot_name
		for worn_entry in worn:
			if int(worn_entry.get("slot_index", 0)) == target:
				replaced = worn_entry.get("item", {})
				outcome = "replaces %s" % str(replaced.get("template", {}).get("name", slot_name))
		if replaced.is_empty() and capacity > 1:
			outcome = "goes into free %s slot %d / %d" % [slot_name, target + 1, capacity]
		_tooltip.show_equipment(_hovered_item, entry.get("item", {}), caption, outcome, replaced, _equipped, hint)
	_tooltip.follow(get_global_mouse_position())


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
	var is_equipped := _equipped_item_ids.has(ApiClient.id_string(_selected_item.get("id")))
	detail_name.text = str(template.get("name", "Unknown Item"))
	detail_type.text = "%s  •  Required level %d" % [item_type.replace("_", " ").capitalize(), int(template.get("minimum_level", 1))]
	detail_icon.texture = ItemIcons.for_template(template)
	detail_state.text = _item_state_text(_selected_item, is_equipped)
	detail_stats.text = _item_stats_text(_selected_item)
	detail_description.text = str(template.get("description", "No description available."))
	var action := item_action(_selected_item)
	action_button.text = str(action.label)
	action_button.disabled = _is_loading or action.kind in ["none", "battle", "restore"]


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
		lines.append("AURORA  %s +%s%s" % [str(line.get("stat_type", "")).to_upper(), ItemTooltip.plain_number(float(line.get("value", 0))), suffix])
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


func _on_back_pressed() -> void:
	SceneRouter.go_to(SceneRouter.HUB)


func _on_enhancement_pressed() -> void:
	SceneRouter.go_to(SceneRouter.ENHANCEMENT)
