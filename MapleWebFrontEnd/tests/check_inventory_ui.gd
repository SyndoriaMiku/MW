extends Node

## Inventory: what a double click does per item, which slot equipping takes,
## the hover comparison (cycled with a middle click for rings), and the shared
## stat comparison.

const PORT := 18769

var _server := FakeHttpServer.new()
var _posts: Array = []


func _ready() -> void:
	if not _check_stat_changes() or not await _check_rules() or not await _check_screen():
		return
	print("INVENTORY_UI_OK posts=%s" % [_posts])
	get_tree().quit(0)


func _ring(item_id: int, att: int) -> Dictionary:
	return {"id": item_id, "quantity": 1, "template": {"id": 30 + item_id, "name": "Ring %d" % item_id, "item_type": "ring", "att_boost": att}}


func _check_stat_changes() -> bool:
	var candidate := {"template": {"att_boost": 10}, "aurora_lines": [{"stat_type": "str", "line_type": "flat", "value": 1.0}]}
	var current := {"template": {"att_boost": 6, "str_boost": 3}}
	var changes := ItemTooltip.stat_changes(candidate, current)
	if changes != [["STR", -2.0], ["ATT", 4.0]]:
		return _fail("STAT_CHANGES_FAILED %s" % [changes])
	if ItemTooltip.stat_changes(candidate, {}) != [["STR", 1.0], ["ATT", 10.0]]:
		return _fail("EMPTY_SLOT_CHANGES_FAILED")
	if not ItemTooltip.stat_changes_bbcode(changes).contains("+4"):
		return _fail("STAT_CHANGES_TEXT_FAILED")
	return true


func _check_rules() -> bool:
	var screen: Control = load("res://src/features/inventory/presentation/inventory_screen.tscn").instantiate()
	screen._slot_capacity = {"ring": 4, "pendant": 2}
	screen.set_equipped([
		{"slot_index": 1, "item": _ring(2, 5)},
		{"slot_index": 0, "item": _ring(1, 4)},
	])
	if screen.target_slot_index("ring", 0) != 2 or screen.target_slot_index("weapon", 0) != 0:
		return _fail("FREE_SLOT_RULE_FAILED")
	screen.set_equipped([
		{"slot_index": 0, "item": _ring(1, 4)}, {"slot_index": 1, "item": _ring(2, 5)},
		{"slot_index": 2, "item": _ring(3, 6)}, {"slot_index": 3, "item": _ring(4, 7)},
	])
	if screen.target_slot_index("ring", 2) != 2 or screen.target_slot_index("ring", 5) != 1:
		return _fail("FULL_SLOTS_REPLACE_COMPARED_FAILED")
	var actions := {
		"equip": _ring(9, 1),
		"unequip": _ring(1, 4),
		"aurora": {"id": 50, "template": {"name": "Gold Essence", "item_type": "use", "use_kind": "aurora_modifier"}},
		"use": {"id": 51, "template": {"name": "EXP Charm", "item_type": "use", "use_kind": "timed_buff"}},
		"battle": {"id": 52, "template": {"name": "Red Potion", "item_type": "use", "use_kind": "battle"}},
		"none": {"id": 53, "template": {"name": "Slime Jelly", "item_type": "etc"}},
	}
	for kind in actions:
		if screen.item_action(actions[kind]).kind != kind:
			return _fail("ITEM_ACTION_FAILED %s" % kind)
	var card: Control = screen._create_item_card(_ring(9, 1))
	if not card is InventoryItemCard or card.get_child_count() == 0:
		return _fail("INVENTORY_CARD_BUILD_FAILED")
	card.free()
	screen.free()
	return true


func _check_screen() -> bool:
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		return _fail("FAKE_SERVER_LISTEN_FAILED")
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.base_url = _server.base_url(PORT)
	SessionStore.begin_session("wearer", "token", "")
	var screen: Control = load("res://src/features/inventory/presentation/inventory_screen.tscn").instantiate()
	add_child(screen)
	if not await _wait_for(func(): return screen.item_grid.get_child_count() == 6 and not screen._is_loading):
		return _fail("INVENTORY_LOAD_FAILED %s" % screen.status_label.text)
	if screen.capacity_for("ring") != 4:
		return _fail("SLOT_CAPACITY_NOT_LOADED")

	var new_ring: InventoryItemCard = _card(screen, "Ring 9")
	new_ring.hover_started.emit(new_ring)
	if not screen._tooltip.visible or screen.compare_entry(new_ring.item).get("slot_index") != 0:
		return _fail("HOVER_COMPARE_FAILED")
	new_ring.compare_cycled.emit(new_ring)
	new_ring.compare_cycled.emit(new_ring)
	if screen.compare_entry(new_ring.item).get("slot_index") != 2:
		return _fail("MIDDLE_CLICK_CYCLE_FAILED")
	new_ring.activated.emit(new_ring)
	if not await _wait_for(func(): return _posts.has("/api/inventory/9/equip/ slot 2") and not screen._is_loading):
		return _fail("EQUIP_INTO_COMPARED_SLOT_FAILED %s" % [_posts])

	var charm: InventoryItemCard = _card(screen, "EXP Charm")
	charm.hover_started.emit(charm)
	if not screen._tooltip.visible:
		return _fail("SIMPLE_TOOLTIP_FAILED")
	charm.activated.emit(charm)
	if not await _wait_for(func(): return _posts.has("/api/inventory/51/use/") and not screen._is_loading):
		return _fail("USE_BUFF_FAILED %s" % [_posts])
	screen.queue_free()
	return true


func _card(screen: Control, name: String) -> InventoryItemCard:
	for card in screen.item_grid.get_children():
		if str(card.item.get("template", {}).get("name")) == name:
			return card
	return null


func _handle(path: String, head: String, payload: Variant) -> Array:
	if head.begins_with("POST"):
		_posts.append("%s slot %d" % [path, int(payload.slot_index)] if payload is Dictionary and payload.has("slot_index") else path)
		return [200, {"status": "Done."}]
	if path == "/api/inventory/slots/":
		return [200, {"count": 2, "next": null, "results": [
			{"id": 11, "slot_type": "ring", "max_count": 4, "allowed_item_types": ["ring"]},
			{"id": 22, "slot_type": "pendant", "max_count": 2, "allowed_item_types": ["pendant"]},
		]}]
	if path == "/api/inventory/":
		return [200, {"count": 6, "next": null, "results": [
			_ring(1, 4), _ring(2, 5), _ring(3, 6), _ring(4, 7), _ring(9, 12),
			{"id": 51, "quantity": 2, "template": {"id": 70, "name": "EXP Charm", "item_type": "use", "use_kind": "timed_buff", "description": "x2 EXP for 30 minutes."}},
		]}]
	if path == "/api/inventory/equipped/":
		return [200, {"count": 4, "next": null, "results": [
			{"slot": 11, "slot_index": 0, "item": _ring(1, 4)}, {"slot": 11, "slot_index": 1, "item": _ring(2, 5)},
			{"slot": 11, "slot_index": 2, "item": _ring(3, 6)}, {"slot": 11, "slot_index": 3, "item": _ring(4, 7)},
		]}]
	return [404, {"detail": "Not found."}]


func _wait_for(condition: Callable, timeout_seconds: float = 10.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(timeout_seconds * 1000)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await get_tree().process_frame
	return true


func _fail(code: String) -> bool:
	printerr(code)
	get_tree().quit(1)
	return false
