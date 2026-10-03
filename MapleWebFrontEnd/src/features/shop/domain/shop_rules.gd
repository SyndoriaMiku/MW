class_name ShopRules
extends RefCounted

## Rules the shop screen needs before calling the backend
## (MapleWebBackEnd/apps/shops and the inventory sell/buy back endpoints).

## Backend cap on one purchase request (shops/serializers.py MAX_QUANTITY_PER_REQUEST).
const MAX_QUANTITY_PER_REQUEST := 999
const STACKABLE_TYPES := ["use", "etc"]


static func is_stackable(template: Dictionary) -> bool:
	return str(template.get("item_type", "")) in STACKABLE_TYPES


static func currency(category: Dictionary) -> String:
	return str(category.get("currency_type", "lumis"))


static func balance(profile: Dictionary, currency_type: String) -> int:
	return int(profile.get(currency_type, 0))


## The level a shop item needs: its own or its category's, whichever is higher.
static func required_level(shop_item: Dictionary, category: Dictionary) -> int:
	return maxi(int(shop_item.get("required_level", 1)), int(category.get("required_level", 1)))


## How many more the player may buy in the current period, or -1 for no limit.
static func remaining_limit(shop_item: Dictionary) -> int:
	var stock := int(shop_item.get("stock", 0))
	if stock <= 0:
		return -1
	return maxi(0, stock - int(shop_item.get("current_bought", 0)))


## The largest quantity the player can buy now: limited by money, the purchase
## limit and the backend's per-request cap. 0 means the item cannot be bought.
static func max_buy_quantity(shop_item: Dictionary, money: int) -> int:
	var price := int(shop_item.get("price", 0))
	var result := MAX_QUANTITY_PER_REQUEST
	if price > 0:
		result = mini(result, floori(float(money) / price))
	var remaining := remaining_limit(shop_item)
	if remaining >= 0:
		result = mini(result, remaining)
	return maxi(0, result)


## Why the player cannot buy this now, or "" when they can.
static func buy_problem(shop_item: Dictionary, category: Dictionary, profile: Dictionary, character_level: int) -> String:
	var needed := required_level(shop_item, category)
	if character_level < needed:
		return "Requires level %d." % needed
	if remaining_limit(shop_item) == 0:
		return "Purchase limit reached for now."
	if max_buy_quantity(shop_item, balance(profile, currency(category))) <= 0:
		return "Not enough %s." % currency_label(currency(category))
	return ""


## Why an inventory item cannot be sold, or "" when it can.
static func sell_problem(item: Dictionary, equipped_ids: Dictionary) -> String:
	var template: Dictionary = item.get("template", {})
	if equipped_ids.has(ApiClient.id_string(item.get("id"))):
		return "Unequip it before selling."
	if not bool(template.get("is_sellable", true)):
		return "This item cannot be sold."
	if bool(item.get("is_destroyed", false)):
		return "Destroyed items cannot be sold."
	return ""


static func sell_value(item: Dictionary, quantity: int) -> int:
	return maxi(0, int(item.get("template", {}).get("sell_price", 0))) * quantity


static func currency_label(currency_type: String) -> String:
	return "Nova" if currency_type == "nova" else "Lumis"


static func format_number(value: int) -> String:
	var digits := str(absi(value))
	var formatted := ""
	while digits.length() > 3:
		formatted = "," + digits.right(3) + formatted
		digits = digits.left(digits.length() - 3)
	return ("-" if value < 0 else "") + digits + formatted
