extends Node

## Shop rules, and the shop screen against a fake backend: double-click to buy
## (with a quantity for stackable items), to sell from the bag, and to buy back.

const PORT := 18767

var _server := FakeHttpServer.new()
var _calls: Array = []


func _ready() -> void:
	if not _check_rules() or not await _check_screen():
		return
	print("SHOP_OK calls=%s" % [_calls])
	get_tree().quit(0)


func _check_rules() -> bool:
	var potion := {"price": 50, "stock": 0, "current_bought": 0, "required_level": 1}
	if ShopRules.max_buy_quantity(potion, 120) != 2 or ShopRules.max_buy_quantity({"price": 0}, 0) != ShopRules.MAX_QUANTITY_PER_REQUEST:
		return _fail("MAX_BUY_MONEY_FAILED")
	if ShopRules.max_buy_quantity({"price": 1, "stock": 5, "current_bought": 4}, 999) != 1 or ShopRules.remaining_limit(potion) != -1:
		return _fail("MAX_BUY_LIMIT_FAILED")
	var category := {"currency_type": "lumis", "required_level": 10}
	if not ShopRules.buy_problem(potion, category, {"lumis": 1000}, 5).contains("level 10"):
		return _fail("BUY_LEVEL_RULE_FAILED")
	if not ShopRules.buy_problem(potion, {"currency_type": "nova"}, {"lumis": 1000, "nova": 10}, 50).contains("Nova"):
		return _fail("BUY_MONEY_RULE_FAILED")
	var sword := {"id": 7.0, "template": {"is_sellable": true, "item_type": "weapon"}}
	if not ShopRules.sell_problem(sword, {"7": true}).contains("Unequip") or not ShopRules.sell_problem({"template": {"is_sellable": false}}, {}).contains("cannot be sold"):
		return _fail("SELL_RULE_FAILED")
	if not ShopRules.is_stackable({"item_type": "use"}) or ShopRules.is_stackable({"item_type": "weapon"}) or ShopRules.format_number(1234567) != "1,234,567":
		return _fail("RULE_HELPERS_FAILED")
	return true


func _check_screen() -> bool:
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		return _fail("FAKE_SERVER_LISTEN_FAILED")
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.base_url = _server.base_url(PORT)
	SessionStore.begin_session("shopper", "token", "")

	var screen: Control = load("res://src/features/shop/presentation/shop_screen.tscn").instantiate()
	add_child(screen)
	if not await _wait_for(func(): return screen.shop_grid.get_child_count() == 2 and not screen._busy):
		return _fail("SHOP_LOAD_FAILED status=%s" % screen.status_label.text)
	if screen.category_list.get_child_count() != 1:
		return _fail("INACTIVE_CATEGORY_SHOWN")

	# Stackable: a double click asks how many.
	var potion_card: ShopCard = screen.shop_grid.get_child(0)
	potion_card.activated.emit(potion_card)
	if not screen.trade_dialog.visible or not screen.quantity_row.visible or screen.quantity_spin.max_value != 20:
		return _fail("BUY_QUANTITY_DIALOG_FAILED max=%s" % screen.quantity_spin.max_value)
	screen.quantity_spin.value = 3
	if not screen.dialog_total.text.contains("150"):
		return _fail("BUY_TOTAL_FAILED %s" % screen.dialog_total.text)
	screen.trade_dialog.hide()
	screen.trade_dialog.confirmed.emit()
	if not await _wait_for(func(): return _called("POST /api/shops/items/1/buy/ 3") and not screen._busy):
		return _fail("BUY_STACK_FAILED %s" % [_calls])

	# Equipment: a double click buys one right away.
	var hammer_card: ShopCard = screen.shop_grid.get_child(1)
	hammer_card.activated.emit(hammer_card)
	if screen.trade_dialog.visible or not await _wait_for(func(): return _called("POST /api/shops/items/2/buy/ 1") and not screen._busy):
		return _fail("BUY_EQUIPMENT_FAILED %s" % [_calls])

	# Bag: an equipped item cannot be sold; a stack asks how many to sell.
	var equipped_row: ShopCard = screen.bag_list.get_child(1)
	equipped_row.activated.emit(equipped_row)
	if screen.trade_dialog.visible or not screen.status_label.text.contains("Unequip"):
		return _fail("SELL_EQUIPPED_NOT_BLOCKED")
	var stack_row: ShopCard = screen.bag_list.get_child(0)
	stack_row.activated.emit(stack_row)
	if not screen.trade_dialog.visible or screen.quantity_spin.max_value != 5 or not screen.dialog_message.text.contains("BUY BACK"):
		return _fail("SELL_DIALOG_FAILED")
	screen.quantity_spin.value = 2
	screen.trade_dialog.hide()
	screen.trade_dialog.confirmed.emit()
	if not await _wait_for(func(): return _called("POST /api/inventory/10/sell/ 2") and not screen._busy):
		return _fail("SELL_FAILED %s" % [_calls])

	# Buy back: a double click asks to confirm the price.
	screen._show_buyback()
	var sold_card: ShopCard = screen.shop_grid.get_child(0)
	sold_card.activated.emit(sold_card)
	if not screen.trade_dialog.visible or screen.quantity_row.visible:
		return _fail("BUYBACK_DIALOG_FAILED")
	screen.trade_dialog.hide()
	screen.trade_dialog.confirmed.emit()
	if not await _wait_for(func(): return _called("POST /api/inventory/buyback/5/repurchase/") and not screen._busy):
		return _fail("BUYBACK_FAILED %s" % [_calls])
	screen.queue_free()
	return true


func _handle(path: String, head: String, payload: Variant) -> Array:
	var method := head.get_slice(" ", 0)
	if method == "POST":
		var quantity: Variant = payload.get("quantity") if payload is Dictionary else null
		_calls.append("POST %s %d" % [path, int(quantity)] if quantity != null else "POST " + path)
	if path == "/api/characters/my/":
		return [200, {"id": "c1", "name": "Shopper", "level": 10}]
	if path == "/api/users/profile/":
		return [200, {"username": "shopper", "lumis": 1000, "nova": 0}]
	if path.begins_with("/api/shops/categories/"):
		return [200, {"count": 2, "next": null, "results": [
			{"id": 1, "name": "General Store", "order": 1, "currency_type": "lumis", "required_level": 1, "is_active": true},
			{"id": 2, "name": "Closed Event", "order": 2, "currency_type": "lumis", "required_level": 1, "is_active": false},
		]}]
	if path.begins_with("/api/shops/items/") and method == "GET":
		return [200, {"count": 2, "next": null, "results": [
			{"id": 1, "category": 1, "price": 50, "stock": 0, "current_bought": 0, "order": 1, "required_level": 1,
				"item_template": {"id": 2, "name": "Copper Essence", "item_type": "use", "description": "A gem."}},
			{"id": 2, "category": 1, "price": 300, "stock": 0, "current_bought": 0, "order": 2, "required_level": 1,
				"item_template": {"id": 1, "name": "Copper Hammer", "item_type": "weapon"}},
		]}]
	if path.ends_with("/buy/"):
		return [200, {"detail": "Successfully purchased."}]
	if path == "/api/inventory/":
		return [200, {"count": 2, "next": null, "results": [
			{"id": 10, "quantity": 5, "template": {"id": 2, "name": "Copper Essence", "item_type": "use", "sell_price": 5, "is_sellable": true}},
			{"id": 11, "quantity": 1, "template": {"id": 1, "name": "Copper Hammer", "item_type": "weapon", "sell_price": 40, "is_sellable": true}},
		]}]
	if path == "/api/inventory/equipped/":
		return [200, {"count": 1, "next": null, "results": [{"slot_index": 0, "item": {"id": 11}}]}]
	if path.ends_with("/sell/"):
		return [200, {"status": "Item sold.", "lumis_gained": 10, "lumis": 1010, "buyback_id": 6}]
	if path == "/api/inventory/buyback/":
		return [200, {"count": 1, "next": null, "results": [
			{"id": 5, "quantity": 1, "price": 40, "lumen_ascend_level": 2, "aurora_level": 0,
				"template": {"id": 1, "name": "Copper Hammer", "item_type": "weapon"}},
		]}]
	if path.ends_with("/repurchase/"):
		return [200, {"status": "Item bought back.", "lumis": 960, "item": {"id": 12}}]
	return [404, {"detail": "Not found."}]


func _called(entry: String) -> bool:
	return _calls.has(entry)


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
