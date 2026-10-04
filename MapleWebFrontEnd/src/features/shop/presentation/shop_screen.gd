extends Control

## NPC shop: buy from shop categories, sell from the bag, and buy back recent
## sales. A double click acts on an item; stackable items and sales ask for a
## quantity first.

@onready var back_button: Button = %BackButton
@onready var refresh_button: Button = %RefreshButton
@onready var currency_label: Label = %CurrencyLabel
@onready var category_list: VBoxContainer = %CategoryList
@onready var buyback_button: Button = %BuybackButton
@onready var shop_title: Label = %ShopTitle
@onready var shop_hint: Label = %ShopHint
@onready var shop_grid: GridContainer = %ShopGrid
@onready var shop_empty: Label = %ShopEmpty
@onready var shop_detail: Label = %ShopDetail
@onready var buy_button: Button = %BuyButton
@onready var bag_title: Label = %BagTitle
@onready var bag_list: VBoxContainer = %BagList
@onready var bag_empty: Label = %BagEmpty
@onready var sell_button: Button = %SellButton
@onready var status_label: Label = %StatusLabel
@onready var trade_dialog: ConfirmationDialog = %TradeDialog
@onready var dialog_message: Label = %DialogMessage
@onready var quantity_row: HBoxContainer = %QuantityRow
@onready var quantity_slider: HSlider = %QuantitySlider
@onready var quantity_spin: SpinBox = %QuantitySpin
@onready var max_button: Button = %MaxButton
@onready var dialog_total: Label = %DialogTotal

var _profile: Dictionary = {}
var _character_level := 1
var _categories: Array = []
var _category: Dictionary = {}
var _showing_buyback := false
var _shop_items: Array = []
var _bag: Array = []
var _equipped_ids: Dictionary = {}
var _buyback: Array = []
var _selected_shop: Dictionary = {}
var _selected_bag: Dictionary = {}
var _category_group := ButtonGroup.new()
var _busy := false
var _dialog_action: Callable
var _dialog_unit_price := 0
var _dialog_total_format := ""


func _ready() -> void:
	HubEmbed.adapt(self, [back_button], $Margin)
	back_button.pressed.connect(SceneRouter.go_to.bind(SceneRouter.HUB))
	refresh_button.pressed.connect(func():
		GameCache.clear_all()
		_load_all()
	)
	buyback_button.button_group = _category_group
	buyback_button.pressed.connect(_show_buyback)
	buy_button.pressed.connect(func(): _activate_shop_entry(_selected_shop))
	sell_button.pressed.connect(func(): _request_sell(_selected_bag))
	quantity_slider.value_changed.connect(_on_quantity_changed.bind(quantity_slider))
	quantity_spin.value_changed.connect(_on_quantity_changed.bind(quantity_spin))
	max_button.pressed.connect(func(): quantity_spin.value = quantity_spin.max_value)
	trade_dialog.confirmed.connect(func(): _dialog_action.call(int(quantity_spin.value)))
	_render_selection()
	if not SceneRouter.require_session():
		return
	await _load_all()


## Called by the hub each time this page is shown again.
func reload_page() -> void:
	await _load_all()


func _load_all() -> void:
	if _busy:
		return
	_set_busy(true, "Loading the shop...")
	var character_response: Dictionary = await GameCache.get_json("characters/my/")
	if character_response.get("ok", false):
		SessionStore.character = character_response.data
		_character_level = int(character_response.data.get("level", 1))
	if not await _load_profile() or not await _load_bag() or not await _load_buyback():
		return
	var categories_response: Dictionary = await GameCache.get_all("shops/categories/")
	if not _accept(categories_response, "Unable to load the shop."):
		return
	_categories = categories_response.data.filter(func(category): return bool(category.get("is_active", true)))
	_categories.sort_custom(func(a, b): return int(a.get("order", 0)) < int(b.get("order", 0)))
	_render_categories()
	_set_busy(false, "Welcome! Double-click an item to buy it, or an item in your bag to sell it.")
	if _showing_buyback:
		_show_buyback()
	elif not _categories.is_empty():
		var current := _find_by_id(_categories, _category.get("id"))
		await _show_category(current if not current.is_empty() else _categories[0])
	else:
		_show_empty_shop()


func _load_profile() -> bool:
	var response: Dictionary = await GameCache.get_json("users/profile/")
	if not _accept(response, "Unable to load your wallet."):
		return false
	_profile = response.data
	currency_label.text = "LUMIS  %s     NOVA  %s" % [
		ShopRules.format_number(int(_profile.get("lumis", 0))),
		ShopRules.format_number(int(_profile.get("nova", 0))),
	]
	return true


func _load_bag() -> bool:
	var inventory_response: Dictionary = await GameCache.get_all("inventory/")
	if not _accept(inventory_response, "Unable to load your bag."):
		return false
	var equipped_response: Dictionary = await GameCache.get_all("inventory/equipped/")
	if not _accept(equipped_response, "Unable to load your equipment."):
		return false
	_bag = inventory_response.data
	_equipped_ids.clear()
	for equipped in equipped_response.data:
		_equipped_ids[ApiClient.id_string(equipped.get("item", {}).get("id"))] = true
	_selected_bag = _find_by_id(_bag, _selected_bag.get("id"))
	_render_bag()
	return true


func _load_buyback() -> bool:
	var response: Dictionary = await GameCache.get_all("inventory/buyback/")
	# A backend without buy back still lets the player buy and sell.
	var supported := int(response.get("status", 0)) != 404
	buyback_button.disabled = not supported
	buyback_button.tooltip_text = "Buy back items you sold by mistake." if supported else "The server does not support buy back yet."
	if not supported:
		_buyback = []
		return true
	if not _accept(response, "Unable to load your recent sales."):
		return false
	_buyback = response.data
	buyback_button.text = "↺  BUY BACK  (%d)" % _buyback.size() if not _buyback.is_empty() else "↺  BUY BACK"
	return true


func _render_categories() -> void:
	_clear(category_list)
	for category in _categories:
		var button := Button.new()
		button.toggle_mode = true
		button.theme_type_variation = &"ListItemButton"
		button.button_group = _category_group
		button.custom_minimum_size = Vector2(0, 46)
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		var level := int(category.get("required_level", 1))
		button.text = "%s%s" % [str(category.get("name", "Shop")), "   Lv.%d" % level if level > 1 else ""]
		button.tooltip_text = "Pays with %s" % ShopRules.currency_label(ShopRules.currency(category))
		button.set_meta("category_id", ApiClient.id_string(category.get("id")))
		button.pressed.connect(_show_category.bind(category))
		category_list.add_child(button)


func _show_category(category: Dictionary) -> void:
	_showing_buyback = false
	_category = category
	_selected_shop = {}
	for button in category_list.get_children():
		button.set_pressed_no_signal(button.get_meta("category_id", "") == ApiClient.id_string(category.get("id")))
	shop_title.text = "%s  •  PAYS WITH %s" % [str(category.get("name", "Shop")).to_upper(), ShopRules.currency_label(ShopRules.currency(category)).to_upper()]
	shop_hint.text = "Double-click an item to buy it. Stackable items ask how many you want."
	var response: Dictionary = await GameCache.get_all("shops/items/?category=%s" % ApiClient.id_string(category.get("id")))
	if not _accept(response, "Unable to load this category."):
		return
	_shop_items = response.data
	_shop_items.sort_custom(func(a, b): return int(a.get("order", 0)) < int(b.get("order", 0)))
	_render_shop()


func _show_buyback() -> void:
	_showing_buyback = true
	_selected_shop = {}
	buyback_button.set_pressed_no_signal(true)
	shop_title.text = "BUY BACK"
	shop_hint.text = "The last 10 items you sold. Double-click one to buy it back for the price it sold for."
	_render_shop()


func _show_empty_shop() -> void:
	shop_title.text = "SHOP"
	shop_hint.text = "No shop is open right now."
	_shop_items = []
	_render_shop()


func _render_shop() -> void:
	_clear(shop_grid)
	var entries: Array = _buyback if _showing_buyback else _shop_items
	for entry in entries:
		var card := _buyback_card(entry) if _showing_buyback else _shop_card(entry)
		card.data = entry
		card.selected.connect(_on_shop_card_selected)
		card.activated.connect(func(clicked: ShopCard): _activate_shop_entry(clicked.data))
		card.set_selected(ApiClient.id_string(entry.get("id")) == ApiClient.id_string(_selected_shop.get("id")))
		shop_grid.add_child(card)
	shop_empty.visible = entries.is_empty()
	shop_empty.text = "You have not sold anything recently." if _showing_buyback else "This category is empty."
	_render_selection()


func _shop_card(shop_item: Dictionary) -> ShopCard:
	var template: Dictionary = shop_item.get("item_template", {})
	var details := PackedStringArray()
	var level := ShopRules.required_level(shop_item, _category)
	if level > 1:
		details.append("Lv.%d" % level)
	var remaining := ShopRules.remaining_limit(shop_item)
	if remaining >= 0:
		details.append("%d left" % remaining)
	var problem := ShopRules.buy_problem(shop_item, _category, _profile, _character_level)
	var card := ShopCard.new(
		ItemIcons.for_template(template),
		str(template.get("name", "Item")),
		PackedStringArray([_price_text(int(shop_item.get("price", 0)), ShopRules.currency(_category)), "  •  ".join(details)]),
		false,
		not problem.is_empty(),
	)
	card.tooltip_text = problem if not problem.is_empty() else str(template.get("description", ""))
	return card


func _buyback_card(entry: Dictionary) -> ShopCard:
	var template: Dictionary = entry.get("template", {})
	var details := PackedStringArray(["×%d" % int(entry.get("quantity", 1))])
	if int(entry.get("lumen_ascend_level", 0)) > 0:
		details.append("Lumen +%d" % int(entry.lumen_ascend_level))
	if int(entry.get("aurora_level", 0)) > 0:
		details.append("Aurora %d" % int(entry.aurora_level))
	var affordable := int(_profile.get("lumis", 0)) >= int(entry.get("price", 0))
	var card := ShopCard.new(
		ItemIcons.for_template(template),
		str(template.get("name", "Item")),
		PackedStringArray([_price_text(int(entry.get("price", 0)), "lumis"), "  •  ".join(details)]),
		false,
		not affordable,
	)
	card.tooltip_text = "" if affordable else "Not enough Lumis."
	return card


func _render_bag() -> void:
	_clear(bag_list)
	var count := 0
	for item in _bag:
		var template: Dictionary = item.get("template", {})
		var quantity := int(item.get("quantity", 1))
		count += quantity
		var problem := ShopRules.sell_problem(item, _equipped_ids)
		var lines := PackedStringArray()
		if problem.is_empty():
			lines.append("Sells for %s each" % _price_text(ShopRules.sell_value(item, 1), "lumis") if quantity > 1 else "Sells for %s" % _price_text(ShopRules.sell_value(item, 1), "lumis"))
		else:
			lines.append(problem)
		var card := ShopCard.new(
			ItemIcons.for_template(template),
			"%s%s" % [str(template.get("name", "Item")), "  ×%d" % quantity if quantity > 1 else ""],
			lines,
			true,
			not problem.is_empty(),
		)
		card.data = item
		card.tooltip_text = problem
		card.selected.connect(_on_bag_card_selected)
		card.activated.connect(func(clicked: ShopCard): _request_sell(clicked.data))
		card.set_selected(ApiClient.id_string(item.get("id")) == ApiClient.id_string(_selected_bag.get("id")))
		bag_list.add_child(card)
	bag_empty.visible = _bag.is_empty()
	bag_title.text = "YOUR BAG  •  %d ITEM%s" % [count, "" if count == 1 else "S"]
	_render_selection()


func _on_shop_card_selected(card: ShopCard) -> void:
	_selected_shop = card.data
	for other in shop_grid.get_children():
		other.set_selected(other == card)
	_render_selection()


func _on_bag_card_selected(card: ShopCard) -> void:
	_selected_bag = card.data
	for other in bag_list.get_children():
		other.set_selected(other == card)
	_render_selection()


func _render_selection() -> void:
	buy_button.text = "BUY BACK" if _showing_buyback else "BUY"
	if _selected_shop.is_empty():
		shop_detail.text = "Select an item to see its details."
		buy_button.disabled = true
	elif _showing_buyback:
		var template: Dictionary = _selected_shop.get("template", {})
		shop_detail.text = "%s ×%d  —  buy back for %s." % [str(template.get("name", "Item")), int(_selected_shop.get("quantity", 1)), _price_text(int(_selected_shop.get("price", 0)), "lumis")]
		buy_button.disabled = _busy
	else:
		var template: Dictionary = _selected_shop.get("item_template", {})
		var problem := ShopRules.buy_problem(_selected_shop, _category, _profile, _character_level)
		var description := str(template.get("description", ""))
		shop_detail.text = "%s  —  %s%s%s" % [
			str(template.get("name", "Item")),
			_price_text(int(_selected_shop.get("price", 0)), ShopRules.currency(_category)),
			"\n" + description if not description.is_empty() else "",
			"\n" + problem if not problem.is_empty() else "",
		]
		buy_button.disabled = _busy or not problem.is_empty()
	sell_button.disabled = _busy or _selected_bag.is_empty() or not ShopRules.sell_problem(_selected_bag, _equipped_ids).is_empty()


func _activate_shop_entry(entry: Dictionary) -> void:
	if entry.is_empty() or _busy:
		return
	if _showing_buyback:
		_request_buyback(entry)
	else:
		await _request_buy(entry)


func _request_buy(shop_item: Dictionary) -> void:
	var problem := ShopRules.buy_problem(shop_item, _category, _profile, _character_level)
	if not problem.is_empty():
		status_label.text = problem
		return
	var template: Dictionary = shop_item.get("item_template", {})
	var name := str(template.get("name", "Item"))
	var currency := ShopRules.currency(_category)
	var price := int(shop_item.get("price", 0))
	if ShopRules.is_stackable(template):
		var most := ShopRules.max_buy_quantity(shop_item, ShopRules.balance(_profile, currency))
		_open_dialog("Buy %s" % name, "How many %s do you want to buy?" % name, most, price,
			"TOTAL  %s " + ShopRules.currency_label(currency).to_upper(), _buy.bind(shop_item))
	elif currency == "nova":
		_open_dialog("Buy %s" % name, "Buy %s for %s Nova?" % [name, ShopRules.format_number(price)], 1, price,
			"TOTAL  %s NOVA", _buy.bind(shop_item))
	else:
		await _buy(1, shop_item)


func _buy(quantity: int, shop_item: Dictionary) -> void:
	_set_busy(true, "Buying...")
	var response: Dictionary = await ApiClient.post_json(
		"shops/items/%s/buy/" % ApiClient.id_string(shop_item.get("id")), {"quantity": quantity}
	)
	if not _accept(response, "The purchase failed."):
		return
	var message := str(response.data.get("detail", "Purchased."))
	await _reload_after_trade(true)
	status_label.text = message


func _request_sell(item: Dictionary) -> void:
	if item.is_empty() or _busy:
		return
	var problem := ShopRules.sell_problem(item, _equipped_ids)
	if not problem.is_empty():
		status_label.text = problem
		return
	var template: Dictionary = item.get("template", {})
	var name := str(template.get("name", "Item"))
	var quantity := int(item.get("quantity", 1))
	var unit_price := ShopRules.sell_value(item, 1)
	var message := "Sell %s for %s Lumis?" % [name, ShopRules.format_number(unit_price)]
	if quantity > 1:
		message = "How many %s do you want to sell?" % name
	_open_dialog("Sell %s" % name, message + "\nSold by mistake? Buy it back under BUY BACK.", quantity, unit_price,
		"YOU GET  %s LUMIS", _sell.bind(item))


func _sell(quantity: int, item: Dictionary) -> void:
	_set_busy(true, "Selling...")
	var response: Dictionary = await ApiClient.post_json(
		"inventory/%s/sell/" % ApiClient.id_string(item.get("id")), {"quantity": quantity}
	)
	if not _accept(response, "The sale failed."):
		return
	var gained := int(response.data.get("lumis_gained", 0))
	var name := str(item.get("template", {}).get("name", "item"))
	await _reload_after_trade(false)
	status_label.text = "Sold %d× %s for %s Lumis. Changed your mind? Buy it back under BUY BACK." % [quantity, name, ShopRules.format_number(gained)]


func _request_buyback(entry: Dictionary) -> void:
	var price := int(entry.get("price", 0))
	if int(_profile.get("lumis", 0)) < price:
		status_label.text = "Not enough Lumis to buy this back."
		return
	var name := str(entry.get("template", {}).get("name", "Item"))
	_open_dialog("Buy back %s" % name, "Buy back %d× %s for %s Lumis?" % [int(entry.get("quantity", 1)), name, ShopRules.format_number(price)],
		1, price, "TOTAL  %s LUMIS", _repurchase.bind(entry))


func _repurchase(_quantity: int, entry: Dictionary) -> void:
	_set_busy(true, "Buying back...")
	var response: Dictionary = await ApiClient.post_json(
		"inventory/buyback/%s/repurchase/" % ApiClient.id_string(entry.get("id"))
	)
	if not _accept(response, "The buy back failed."):
		return
	await _reload_after_trade(false)
	status_label.text = "Bought back %s." % str(entry.get("template", {}).get("name", "the item"))


## After any trade the wallet, bag and buy back list may have changed; a
## purchase also moves the item's purchase limit.
func _reload_after_trade(reload_items: bool) -> void:
	if not await _load_profile() or not await _load_bag() or not await _load_buyback():
		return
	_set_busy(false, "")
	if _showing_buyback:
		_selected_shop = _find_by_id(_buyback, _selected_shop.get("id"))
		_render_shop()
	elif reload_items and not _category.is_empty():
		var selected_id: Variant = _selected_shop.get("id")
		await _show_category(_category)
		_selected_shop = _find_by_id(_shop_items, selected_id)
		_render_shop()
	else:
		_render_shop()


## Opens the confirm dialog. With max_quantity > 1 it shows a quantity picker;
## total_format gets the formatted total (unit_price × quantity).
func _open_dialog(title: String, message: String, max_quantity: int, unit_price: int, total_format: String, action: Callable) -> void:
	trade_dialog.title = title
	dialog_message.text = message
	_dialog_action = action
	_dialog_unit_price = unit_price
	_dialog_total_format = total_format
	quantity_row.visible = max_quantity > 1
	quantity_slider.max_value = maxi(1, max_quantity)
	quantity_spin.max_value = maxi(1, max_quantity)
	quantity_spin.value = 1
	quantity_slider.value = 1
	_update_dialog_total()
	trade_dialog.size = Vector2i(440, 0)
	trade_dialog.popup_centered()
	if quantity_row.visible:
		quantity_spin.get_line_edit().grab_focus()
		quantity_spin.get_line_edit().select_all()


func _on_quantity_changed(value: float, source: Range) -> void:
	if source == quantity_slider:
		quantity_spin.set_value_no_signal(value)
	else:
		quantity_slider.set_value_no_signal(value)
	_update_dialog_total()


func _update_dialog_total() -> void:
	dialog_total.text = _dialog_total_format % ShopRules.format_number(_dialog_unit_price * int(quantity_spin.value))


func _accept(response: Dictionary, fallback: String) -> bool:
	if response.get("ok", false):
		return true
	_set_busy(false, ApiClient.error_message(response, fallback))
	return false


func _set_busy(value: bool, message: String) -> void:
	_busy = value
	refresh_button.disabled = value
	back_button.disabled = value
	if not message.is_empty():
		status_label.text = message
	_render_selection()


func _price_text(amount: int, currency: String) -> String:
	return "%s %s" % [ShopRules.format_number(amount), ShopRules.currency_label(currency).to_upper()]


## Removes the children now, not at the end of the frame, so lookups and
## clicks never reach a card that is about to go away.
static func _clear(container: Node) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()


static func _find_by_id(items: Array, id_value: Variant) -> Dictionary:
	var wanted := ApiClient.id_string(id_value)
	if wanted.is_empty():
		return {}
	for item in items:
		if item is Dictionary and ApiClient.id_string(item.get("id")) == wanted:
			return item
	return {}
