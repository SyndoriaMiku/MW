class_name AdventurePage
extends Control

## The world map: pick a region, then a dungeon in one of its locations, and
## enter it. Normal dungeons cost stamina and are played solo; boss dungeons
## are entered by the party leader once per day, week or month. Everything is
## listed in the order set in Studio (`order`). Dungeons without a location
## are listed under "Elsewhere"; servers without regions get one flat list.

signal battle_started
signal stamina_changed

const ELSEWHERE := "elsewhere"
const TIME_LABELS := {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}

var _dungeons: Array = []
var _bosses: Array = []
var _regions: Array = []
var _region_id := ""
var _selected: Dictionary = {}
var _character: Dictionary = {}
var _active_battle: Dictionary = {}
var _party: Variant = null
var _stamina := 0
var _busy := false

var _status: Label
var _regions_row := HBoxContainer.new()
var _region_group := ButtonGroup.new()
var _list: VBoxContainer
var _detail: VBoxContainer
var _detail_name := Label.new()
var _chips := HBoxContainer.new()
var _detail_description := Label.new()
var _detail_rewards := Label.new()
var _detail_reason := Label.new()
var _enter_button := Button.new()
var _resume_banner := PanelContainer.new()
var _resume_text := Label.new()
var _empty := Label.new()


func _init() -> void:
	name = "AdventurePage"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var column := HubWidgets.page_column(self)
	var header := HubWidgets.header("Adventure", load_dungeons)
	_status = header.status
	column.add_child(header.row)
	_regions_row.add_theme_constant_override("separation", 8)
	header.row.add_child(_regions_row)
	header.row.move_child(_regions_row, 1)
	_build_resume_banner(column)
	var content := HBoxContainer.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 16)
	column.add_child(content)
	_list = HubWidgets.scroll_list(content, 420)
	_empty.text = "No dungeon is open yet."
	_empty.theme_type_variation = &"MutedLabel"
	_detail = HubWidgets.detail_card(content)
	_build_detail()


## The empty-state label is out of the tree while the list has rows.
func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and is_instance_valid(_empty) and _empty.get_parent() == null:
		_empty.free()


func _build_resume_banner(column: VBoxContainer) -> void:
	_resume_banner.visible = false
	_resume_banner.add_theme_stylebox_override("panel", M3.box(M3.ERROR_CONTAINER, M3.CORNER_LARGE, 12.0))
	column.add_child(_resume_banner)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	_resume_banner.add_child(row)
	row.add_child(M3.icon_label("swords", 22, M3.ON_ERROR_CONTAINER))
	_resume_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_resume_text.add_theme_color_override("font_color", M3.ON_ERROR_CONTAINER)
	_resume_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(_resume_text)
	var resume := Button.new()
	resume.name = "ResumeButton"
	resume.text = "Resume"
	resume.theme_type_variation = &"DangerButton"
	resume.pressed.connect(func(): SceneRouter.go_to(SceneRouter.BATTLE))
	row.add_child(resume)


func _build_detail() -> void:
	_detail_name.add_theme_font_size_override("font_size", M3.HEADLINE_MEDIUM)
	_detail.add_child(_detail_name)
	_chips.add_theme_constant_override("separation", 8)
	_detail.add_child(_chips)
	_detail_description.theme_type_variation = &"MutedLabel"
	_detail_description.add_theme_font_size_override("font_size", M3.BODY_LARGE)
	_detail_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_detail_description)
	_detail.add_child(HubWidgets.section_label("Rewards"))
	_detail.add_child(_detail_rewards)
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_child(spacer)
	_detail_reason.theme_type_variation = &"ErrorLabel"
	_detail_reason.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_detail_reason)
	_enter_button.name = "EnterButton"
	_enter_button.text = "Enter dungeon"
	_enter_button.theme_type_variation = &"PrimaryButton"
	_enter_button.custom_minimum_size = Vector2(220, 48)
	_enter_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	_enter_button.icon = IconTexture.make("play_arrow", M3.ON_PRIMARY)
	_enter_button.pressed.connect(_on_enter_pressed)
	_detail.add_child(_enter_button)


## The hub hands over what it already knows; `stamina` is the regenerated value.
func set_context(character: Dictionary, stamina: int, active_battle: Dictionary) -> void:
	_character = character
	_stamina = stamina
	_active_battle = active_battle
	_resume_banner.visible = not active_battle.is_empty()
	if not active_battle.is_empty():
		_resume_text.text = "A battle is in progress (turn %d). Finish it before entering another dungeon." % int(active_battle.get("turn_count", 1))
	_render_list()


func load_dungeons() -> void:
	if _busy:
		return
	_set_busy(true, "Loading the world map...")
	var normal_response: Dictionary = await GameCache.get_all("world/normal-dungeons/")
	var boss_response: Dictionary = await GameCache.get_all("world/boss-dungeons/")
	var region_response: Dictionary = await GameCache.get_json("world/regions/")
	if not is_inside_tree():
		return
	if not normal_response.get("ok", false):
		_set_busy(false, ApiClient.error_message(normal_response, "Unable to load dungeons."))
		return
	_dungeons = sorted_by_order(_tagged(ApiClient.unwrap_list(normal_response.data), "normal"))
	_bosses = sorted_by_order(_tagged(ApiClient.unwrap_list(boss_response.get("data", [])), "boss")) if boss_response.get("ok", false) else []
	_regions = build_regions(ApiClient.unwrap_list(region_response.get("data", [])) if region_response.get("ok", false) else [], _dungeons, _bosses)
	if not _bosses.is_empty():
		await _load_party()
		if not is_inside_tree():
			return
	var current := _find_entry(_key(_selected))
	_selected = current if not current.is_empty() else _first_open()
	_region_id = _region_of(_selected) if _region_id.is_empty() or _find_region(_region_id).is_empty() else _region_id
	_set_busy(false, "")
	_render_regions()
	_render_list()


func _load_party() -> void:
	var response: Dictionary = await GameCache.get_json("party/party/my/")
	_party = response.data if response.get("ok", false) and response.data is Dictionary else null


## Regions -> locations -> dungeons, for display: [{"id", "name", "locations":
## [{"name", "dungeons": [entry...]}]}]. Dungeons the map does not place go to
## an "Elsewhere" region; with no map at all there is one "All dungeons" region.
static func build_regions(regions: Array, dungeons: Array, bosses: Array) -> Array:
	var by_key := {}
	for entry in dungeons + bosses:
		by_key[_key(entry)] = entry
	var placed := {}
	var result: Array = []
	for region in sorted_by_order(regions):
		var locations: Array = []
		for location in sorted_by_order(region.get("locations", [])):
			var entries: Array = []
			for summary in location.get("normal_dungeons", []):
				var key := "normal:" + ApiClient.id_string(summary.get("id"))
				if by_key.has(key):
					entries.append(by_key[key])
			for summary in location.get("boss_dungeons", []):
				var key := "boss:" + ApiClient.id_string(summary.get("id"))
				if by_key.has(key):
					entries.append(by_key[key])
			for entry in entries:
				placed[_key(entry)] = true
			if not entries.is_empty():
				locations.append({"name": str(location.get("name", "")), "dungeons": entries})
		if not locations.is_empty():
			result.append({"id": ApiClient.id_string(region.get("id")), "name": str(region.get("name", "Region")), "locations": locations})
	var rest: Array = []
	for entry in dungeons + bosses:
		if not placed.has(_key(entry)):
			rest.append(entry)
	if not rest.is_empty():
		var name := "Elsewhere" if not result.is_empty() else "All dungeons"
		result.append({"id": ELSEWHERE, "name": name, "locations": [{"name": "", "dungeons": rest}]})
	return result


## Entries in their Studio order (`order`, then level, then id, as the backend
## sorts them). Servers without `order` keep the level order.
static func sorted_by_order(entries: Array) -> Array:
	var result := entries.duplicate()
	result.sort_custom(func(a, b):
		for key in ["order", "required_level", "id"]:
			var left := float(a.get(key, 0))
			var right := float(b.get(key, 0))
			if left != right:
				return left < right
		return false
	)
	return result


## Why a normal dungeon cannot be entered right now, "" when it can.
static func block_reason(dungeon: Dictionary, level: int, stamina: int, has_active_battle: bool) -> String:
	if dungeon.is_empty():
		return "Pick a dungeon."
	if has_active_battle:
		return "Finish your current battle first."
	if level < int(dungeon.get("required_level", 1)):
		return "Requires level %d." % int(dungeon.get("required_level", 1))
	if stamina < int(dungeon.get("stamina_cost", 0)):
		return "Not enough stamina (%d needed)." % int(dungeon.get("stamina_cost", 0))
	return ""


## Why a boss dungeon cannot be started, "" when it can. `party` is the
## character's party or null (one is created when entering).
static func boss_block_reason(boss: Dictionary, character: Dictionary, party: Variant, has_active_battle: bool) -> String:
	if has_active_battle:
		return "Finish your current battle first."
	if int(character.get("level", 1)) < int(boss.get("required_level", 1)):
		return "Requires level %d." % int(boss.get("required_level", 1))
	if party is Dictionary:
		if ApiClient.id_string(party.get("leader_id")) != ApiClient.id_string(character.get("id")):
			return "Only your party leader can start a boss."
		var size := int(party.get("member_count", 1))
		if size > int(boss.get("max_party_size", 4)):
			return "Your party is too big (%d of %d)." % [size, int(boss.get("max_party_size", 4))]
	return ""


func _reason_for(entry: Dictionary) -> String:
	if entry.is_empty():
		return "Pick a dungeon."
	if str(entry.get("kind")) == "boss":
		return boss_block_reason(entry, _character, _party, not _active_battle.is_empty())
	return block_reason(entry, int(_character.get("level", 1)), _stamina, not _active_battle.is_empty())


func _render_regions() -> void:
	HubWidgets.clear(_regions_row)
	if _regions.size() < 2:
		return
	for region in _regions:
		var chip := Button.new()
		chip.name = "Region" + str(region.id).capitalize().replace(" ", "")
		chip.text = str(region.name)
		chip.toggle_mode = true
		chip.button_group = _region_group
		chip.theme_type_variation = &"ChipButton"
		chip.focus_mode = Control.FOCUS_NONE
		chip.button_pressed = str(region.id) == _region_id
		chip.set_meta("region_id", str(region.id))
		chip.pressed.connect(_select_region.bind(str(region.id)))
		_regions_row.add_child(chip)


## Shows region `region_id`, picking its first dungeon the character can
## enter (or its first dungeon) unless the selection is already there.
func _select_region(region_id: String) -> void:
	_region_id = region_id
	if _region_of(_selected) != region_id:
		var level := int(_character.get("level", 1))
		var first := {}
		var first_open := {}
		for location in _find_region(region_id).get("locations", []):
			for entry in location.dungeons:
				if first.is_empty():
					first = entry
				if first_open.is_empty() and int(entry.get("required_level", 1)) <= level:
					first_open = entry
		_selected = first_open if not first_open.is_empty() else first
	for chip in _regions_row.get_children():
		chip.set_pressed_no_signal(chip.get_meta("region_id", "") == region_id)
	_render_list()


func _render_list() -> void:
	HubWidgets.clear(_list, [_empty])
	var region := _find_region(_region_id)
	if region.is_empty() and not _regions.is_empty():
		region = _regions[0]
	_empty.visible = region.is_empty() and not _busy
	if region.is_empty():
		_list.add_child(_empty)
	var level := int(_character.get("level", 1))
	for location in region.get("locations", []):
		if not str(location.name).is_empty():
			var heading := HBoxContainer.new()
			heading.add_theme_constant_override("separation", 6)
			heading.add_child(M3.icon_label("location_on", 18, M3.PRIMARY))
			heading.add_child(HubWidgets.section_label(str(location.name)))
			_list.add_child(heading)
		for entry in location.dungeons:
			_list.add_child(_dungeon_card(entry, level))
	_render_detail()


func _dungeon_card(entry: Dictionary, level: int) -> Button:
	var boss := str(entry.get("kind")) == "boss"
	var locked := level < int(entry.get("required_level", 1))
	var meta := "Lv. %d+   •   " % int(entry.get("required_level", 1))
	if boss:
		meta += "%s boss  •  up to %d" % [TIME_LABELS.get(str(entry.get("time_type")), "Boss"), int(entry.get("max_party_size", 4))]
	else:
		meta += "%d stamina" % int(entry.get("stamina_cost", 0))
	var card := HubWidgets.list_card(
		"lock" if locked else ("crown" if boss else "castle"), str(entry.get("name", "Dungeon")), meta,
		_key(entry) == _key(_selected), locked, "Boss" if boss else "", M3.TERTIARY
	)
	card.name = "Dungeon" + _key(entry).replace(":", "")
	card.pressed.connect(_select.bind(entry))
	return card


func _select(entry: Dictionary) -> void:
	_selected = entry
	_render_list()


func _render_detail() -> void:
	var has_entry := not _selected.is_empty()
	_detail.get_parent().visible = has_entry
	if not has_entry:
		return
	var boss := str(_selected.get("kind")) == "boss"
	_detail_name.text = str(_selected.get("name", "Dungeon"))
	HubWidgets.clear(_chips)
	_chips.add_child(HubWidgets.chip("military_tech", "Level %d+" % int(_selected.get("required_level", 1))).chip)
	if boss:
		_chips.add_child(HubWidgets.chip("schedule", "Once %s" % {"daily": "a day", "weekly": "a week", "monthly": "a month"}.get(str(_selected.get("time_type")), "per reset")).chip)
		_chips.add_child(HubWidgets.chip("groups", "Party of up to %d" % int(_selected.get("max_party_size", 4))).chip)
	else:
		_chips.add_child(HubWidgets.chip("bolt", "%d stamina  (you have %d)" % [int(_selected.get("stamina_cost", 0)), _stamina]).chip)
	var location: Variant = _selected.get("location")
	if location is Dictionary:
		_chips.add_child(HubWidgets.chip("location_on", str(location.get("name", ""))).chip)
	_detail_description.text = str(_selected.get("description", "")).strip_edges()
	if _detail_description.text.is_empty():
		_detail_description.text = "Defeat the boss with your party." if boss else "Enter the dungeon and defeat every enemy."
	var rewards: Array[String] = []
	if int(_selected.get("exp_reward", 0)) > 0:
		rewards.append("%d EXP" % int(_selected.exp_reward))
	if int(_selected.get("lumis_reward", 0)) > 0:
		rewards.append("%s Lumis" % HubScreen.group_digits(int(_selected.lumis_reward)))
	_detail_rewards.text = "  •  ".join(rewards) + ("  •  item drops" if not rewards.is_empty() else "Item drops")
	var reason := _reason_for(_selected)
	_detail_reason.text = reason
	_detail_reason.visible = not reason.is_empty()
	_enter_button.text = "Challenge boss" if boss else "Enter dungeon"
	_enter_button.disabled = _busy or not reason.is_empty()


func _on_enter_pressed() -> void:
	if _busy or not _reason_for(_selected).is_empty():
		return
	var boss := str(_selected.get("kind")) == "boss"
	_set_busy(true, "Entering %s..." % str(_selected.get("name", "the dungeon")))
	if boss and _party == null:
		# Bosses need a party; a party of one is enough.
		var created: Dictionary = await ApiClient.post_json("party/party/create_party/", {"name": "%s's Party" % str(_character.get("name", "My"))})
		if not is_inside_tree():
			return
		if not created.get("ok", false):
			_set_busy(false, ApiClient.error_message(created, "Unable to create a party."))
			return
		_party = created.data
	var path := "world/%s/%s/enter/" % ["boss-dungeons" if boss else "normal-dungeons", ApiClient.id_string(_selected.get("id"))]
	var response: Dictionary = await ApiClient.post_json(path)
	if not is_inside_tree():
		return
	if not response.get("ok", false):
		var message := ApiClient.error_message(response, "Unable to enter the dungeon.")
		_set_busy(false, message)
		_detail_reason.text = message
		_detail_reason.visible = true
		stamina_changed.emit()
		return
	SessionStore.active_battle_id = ApiClient.id_string(response.get("data", {}).get("combat_instance_id"))
	if SessionStore.active_battle_id.is_empty():
		_set_busy(false, "The server did not return a battle.")
		return
	battle_started.emit()
	SceneRouter.go_to(SceneRouter.BATTLE)


func _set_busy(value: bool, message: String) -> void:
	_busy = value
	_status.text = message
	_render_detail()


## A normal dungeon by id (kept for callers that only know normal dungeons).
func _find(id: Variant) -> Dictionary:
	return _find_entry("normal:" + ApiClient.id_string(id))


func _find_entry(key: String) -> Dictionary:
	for entry in _dungeons + _bosses:
		if _key(entry) == key:
			return entry
	return {}


func _find_region(region_id: String) -> Dictionary:
	for region in _regions:
		if str(region.id) == region_id:
			return region
	return {}


func _region_of(entry: Dictionary) -> String:
	for region in _regions:
		for location in region.locations:
			for candidate in location.dungeons:
				if _key(candidate) == _key(entry):
					return str(region.id)
	return str(_regions[0].id) if not _regions.is_empty() else ""


## The open normal dungeon with the highest required level (the first such one
## in the list), else the first dungeon.
func _first_open() -> Dictionary:
	var level := int(_character.get("level", 1))
	var best: Dictionary = {}
	for dungeon in _dungeons:
		var required := int(dungeon.get("required_level", 1))
		if required <= level and (best.is_empty() or required > int(best.get("required_level", 1))):
			best = dungeon
	if not best.is_empty():
		return best
	var everything := _dungeons + _bosses
	return everything[0] if not everything.is_empty() else {}


static func _tagged(entries: Array, kind: String) -> Array:
	for entry in entries:
		entry["kind"] = kind
	return entries


static func _key(entry: Dictionary) -> String:
	if entry.is_empty():
		return ""
	return "%s:%s" % [str(entry.get("kind", "normal")), ApiClient.id_string(entry.get("id"))]
