extends Control

@onready var back_button: Button = %BackButton
@onready var inventory_button: Button = %InventoryButton
@onready var refresh_button: Button = %RefreshButton
@onready var lumen_menu_button: Button = %LumenMenuButton
@onready var aurora_menu_button: Button = %AuroraMenuButton
@onready var future_menu_button: Button = %FutureMenuButton
@onready var currency_label: Label = %CurrencyLabel
@onready var target_select: OptionButton = %TargetSelect
@onready var target_icon: TextureRect = %TargetIcon
@onready var target_name: Label = %TargetName
@onready var target_state: Label = %TargetState
@onready var system_pages: TabContainer = %SystemPages
@onready var lumen_level: Label = %LumenLevel
@onready var lumen_breakdown: Label = %LumenBreakdown
@onready var lumen_rates: Label = %LumenRates
@onready var lumen_cost: Label = %LumenCost
@onready var lumen_event_info: Label = %LumenEventInfo
@onready var lumen_warning: Label = %LumenWarning
@onready var lumen_button: Button = %LumenButton
@onready var aurora_level: Label = %AuroraLevel
@onready var aurora_lines: Label = %AuroraLines
@onready var essence_select: OptionButton = %EssenceSelect
@onready var reveal_button: Button = %RevealButton
@onready var reroll_button: Button = %RerollButton
@onready var pending_panel: VBoxContainer = %PendingPanel
@onready var pending_lines: Label = %PendingLines
@onready var keep_old_button: Button = %KeepOldButton
@onready var take_new_button: Button = %TakeNewButton
@onready var status_label: Label = %StatusLabel
@onready var result_effect_layer: Control = %ResultEffectLayer
@onready var result_backdrop: ColorRect = %ResultBackdrop
@onready var result_card: PanelContainer = %ResultCard
@onready var result_symbol: Label = %ResultSymbol
@onready var result_title: Label = %ResultTitle
@onready var result_subtitle: Label = %ResultSubtitle

var _items: Array = []
var _equipment: Array = []
var _essences: Array = []
var _selected_item: Dictionary = {}
var _lumen_preview: Dictionary = {}
var _lumen_preview_error := ""
var _pending_roll: Dictionary = {}
var _pending_target_id := ""
var _is_loading := false


func _ready() -> void:
	back_button.pressed.connect(SceneRouter.go_to.bind(SceneRouter.LAUNCHER))
	inventory_button.pressed.connect(SceneRouter.go_to.bind(SceneRouter.INVENTORY))
	refresh_button.pressed.connect(_load_data)
	lumen_menu_button.pressed.connect(_select_system.bind(0))
	aurora_menu_button.pressed.connect(_select_system.bind(1))
	future_menu_button.pressed.connect(_select_system.bind(2))
	target_select.item_selected.connect(_on_target_selected)
	lumen_button.pressed.connect(_on_lumen_pressed)
	reveal_button.pressed.connect(_on_reveal_pressed)
	reroll_button.pressed.connect(_on_reroll_pressed)
	keep_old_button.pressed.connect(_on_confirm_roll.bind("keep_old"))
	take_new_button.pressed.connect(_on_confirm_roll.bind("take_new"))
	for button in [lumen_menu_button, aurora_menu_button, future_menu_button]:
		button.toggle_mode = true
	_select_system(0)
	if not SceneRouter.require_session():
		return
	await _load_data()


func _select_system(index: int) -> void:
	system_pages.current_tab = index
	lumen_menu_button.button_pressed = index == 0
	aurora_menu_button.button_pressed = index == 1
	future_menu_button.button_pressed = index == 2


func _load_data() -> void:
	if _is_loading:
		return
	_set_loading(true, "Loading enhancement data...")
	var selected_id := ApiClient.id_string(_selected_item.get("id"))
	var selected_essence_id := _selected_option_id(essence_select)
	var profile_response: Dictionary = await ApiClient.get_json("users/profile/")
	if not _accept_http(profile_response):
		return
	currency_label.text = "LUMIS  %d" % int(profile_response.get("data", {}).get("lumis", 0))

	var inventory_response: Dictionary = await ApiClient.get_all("inventory/")
	if not _accept_http(inventory_response):
		return
	_items = ApiClient.unwrap_list(inventory_response.get("data", []))
	_equipment = []
	_essences = []
	for item_value in _items:
		if not item_value is Dictionary:
			continue
		var item: Dictionary = item_value
		var template: Dictionary = item.get("template", {})
		var item_type := str(template.get("item_type", ""))
		if ItemTypes.is_equipment(item_type):
			_equipment.append(item)
		elif item_type == "use" and str(template.get("name", "")).to_lower().contains("essence"):
			_essences.append(item)

	_populate_target_select(selected_id)
	_populate_essence_select(selected_essence_id)
	_render_selected_item()
	_is_loading = false
	await _load_lumen_preview()
	_set_loading(false, "Enhancement data synchronized with the server.")


func _populate_target_select(preferred_id: String) -> void:
	target_select.clear()
	var selected_index := -1
	for item in _equipment:
		var template: Dictionary = item.get("template", {})
		var label := "%s  •  Lumen %d  •  Aurora %d" % [
			str(template.get("name", "Unknown Item")),
			int(item.get("lumen_ascend_level", 0)),
			int(item.get("aurora_level", 0)),
		]
		target_select.add_item(label)
		target_select.set_item_metadata(target_select.item_count - 1, ApiClient.id_string(item.get("id")))
		if ApiClient.id_string(item.get("id")) == preferred_id:
			selected_index = target_select.item_count - 1
	if target_select.item_count == 0:
		_selected_item = {}
		return
	if selected_index < 0:
		selected_index = 0
	target_select.select(selected_index)
	_selected_item = _find_item(str(target_select.get_item_metadata(selected_index)))


func _populate_essence_select(preferred_id: String) -> void:
	essence_select.clear()
	var selected_index := -1
	for essence in _essences:
		var template: Dictionary = essence.get("template", {})
		essence_select.add_item("%s  ×%d" % [template.get("name", "Essence"), int(essence.get("quantity", 1))])
		essence_select.set_item_metadata(essence_select.item_count - 1, ApiClient.id_string(essence.get("id")))
		if ApiClient.id_string(essence.get("id")) == preferred_id:
			selected_index = essence_select.item_count - 1
	if essence_select.item_count > 0:
		essence_select.select(maxi(0, selected_index))


func _on_target_selected(index: int) -> void:
	if index < 0:
		return
	_selected_item = _find_item(str(target_select.get_item_metadata(index)))
	_lumen_preview = {}
	_lumen_preview_error = ""
	_render_selected_item()
	await _load_lumen_preview()


func _render_selected_item() -> void:
	if _selected_item.is_empty():
		target_icon.texture = null
		target_name.text = "No equipment available"
		target_state.text = "Equipment in your inventory will appear here."
		lumen_level.text = "—"
		lumen_breakdown.text = "No target item."
		_render_lumen_preview()
		aurora_level.text = "AURORA —"
		aurora_lines.text = "No target item."
		_set_action_availability(false, false, false)
		return
	var template: Dictionary = _selected_item.get("template", {})
	target_icon.texture = ItemIcons.for_template(template)
	target_name.text = str(template.get("name", "Unknown Item"))
	target_state.text = "%s  •  Required Level %d%s" % [
		str(template.get("item_type", "equipment")).capitalize(),
		int(template.get("minimum_level", 1)),
		"  •  DESTROYED" if bool(_selected_item.get("is_destroyed", false)) else "",
	]

	var current_lumen := int(_selected_item.get("lumen_ascend_level", 0))
	var max_lumen := _max_lumen_level(_selected_item)
	var next_lumen := mini(current_lumen + 1, max_lumen) if max_lumen > 0 else current_lumen + 1
	lumen_level.text = "%d  >>>  %d" % [current_lumen, next_lumen]
	lumen_breakdown.text = _lumen_stats_text(_selected_item)
	_render_lumen_preview()

	var current_aurora := int(_selected_item.get("aurora_level", 0))
	aurora_level.text = "AURORA %d" % current_aurora
	var lines: Array = _selected_item.get("aurora_lines", [])
	aurora_lines.text = _format_aurora_lines(lines) if not lines.is_empty() else "No Aurora lines revealed."
	var supports_lumen := template.get("lumen_tier") != null
	var supports_aurora := template.get("aurora_tier") != null
	var is_destroyed := bool(_selected_item.get("is_destroyed", false))
	var preview_cost: Dictionary = _lumen_preview.get("cost", {})
	var lumen_can_ascend := supports_lumen and not is_destroyed and (max_lumen <= 0 or current_lumen < max_lumen) and bool(_lumen_preview.get("success", false)) and bool(preview_cost.get("can_afford", false))
	_set_action_availability(lumen_can_ascend, supports_aurora and lines.is_empty() and not is_destroyed, supports_aurora and not lines.is_empty() and not is_destroyed)
	_render_pending_roll()


func _load_lumen_preview() -> void:
	_lumen_preview = {}
	_lumen_preview_error = ""
	if _selected_item.is_empty():
		_render_selected_item()
		return
	var requested_item_id := ApiClient.id_string(_selected_item.get("id"))
	var template: Dictionary = _selected_item.get("template", {})
	var current_level := int(_selected_item.get("lumen_ascend_level", 0))
	var max_level := _max_lumen_level(_selected_item)
	if template.get("lumen_tier") == null:
		_lumen_preview_error = "This item does not support Lumen Ascend."
		_render_selected_item()
		return
	if bool(_selected_item.get("is_destroyed", false)):
		_lumen_preview_error = "Restore this item before enhancing it."
		_render_selected_item()
		return
	if max_level > 0 and current_level >= max_level:
		_lumen_preview_error = "Maximum Lumen level reached."
		_render_selected_item()
		return
	lumen_rates.text = "Loading current rates..."
	lumen_cost.text = ""
	lumen_event_info.text = ""
	lumen_button.disabled = true
	var response: Dictionary = await ApiClient.get_json(
		"items/lumen/preview/?inventory_item_id=%s" % requested_item_id.uri_encode()
	)
	if requested_item_id != ApiClient.id_string(_selected_item.get("id")):
		return
	if response.get("ok", false):
		var data: Variant = response.get("data", {})
		if data is Dictionary and bool(data.get("success", false)):
			_lumen_preview = data
		else:
			_lumen_preview_error = str(data.get("message", "Lumen preview is unavailable.")) if data is Dictionary else "Lumen preview is unavailable."
	else:
		var error: Dictionary = response.get("error", {})
		_lumen_preview_error = str(error.get("message", "Unable to load Lumen rates."))
	_render_selected_item()


func _render_lumen_preview() -> void:
	if _lumen_preview.is_empty():
		lumen_rates.text = _lumen_preview_error if not _lumen_preview_error.is_empty() else "Select an upgradeable item to view current rates."
		lumen_cost.text = ""
		lumen_event_info.text = ""
		lumen_warning.text = "Rates and cost are calculated by the server."
		return
	var rates: Dictionary = _lumen_preview.get("final_rate_percent", {})
	var cost: Dictionary = _lumen_preview.get("cost", {})
	var level: Dictionary = _lumen_preview.get("level", {})
	lumen_rates.text = "SUCCESS  %s%%     FAILURE  %s%%     DESTROYED  %s%%" % [
		_format_percent(rates.get("success", 0)),
		_format_percent(rates.get("failure", 0)),
		_format_percent(rates.get("heavy_failure", 0)),
	]
	lumen_cost.text = "COST  %s LUMIS     BALANCE  %s" % [
		_format_integer(int(cost.get("amount", 0))),
		_format_integer(int(cost.get("balance", 0))),
	]
	var modifiers: Dictionary = _lumen_preview.get("event_modifiers", {})
	var event_names := PackedStringArray()
	for event_value in modifiers.get("active_events", []):
		if event_value is Dictionary:
			event_names.append(str(event_value.get("name", "Event")))
	var bonus_levels := int(modifiers.get("bonus_levels", 0))
	lumen_event_info.text = "Active event: %s%s" % [
		", ".join(event_names) if not event_names.is_empty() else "None",
		"  •  Success grants +%d levels" % (1 + bonus_levels) if bonus_levels > 0 else "",
	]
	lumen_warning.text = "Success reaches Lumen %d. Heavy failure destroys the item.%s" % [
		int(level.get("on_success", int(level.get("current", 0)) + 1)),
		"  Not enough Lumis." if not bool(cost.get("can_afford", false)) else "",
	]


func _set_action_availability(can_lumen: bool, can_reveal: bool, can_reroll: bool) -> void:
	lumen_button.disabled = _is_loading or not can_lumen
	reveal_button.visible = can_reveal
	reveal_button.disabled = _is_loading or not can_reveal
	reroll_button.visible = not can_reveal
	reroll_button.disabled = _is_loading or not can_reroll or essence_select.item_count == 0 or not _pending_roll.is_empty()
	essence_select.disabled = _is_loading or essence_select.item_count == 0 or not _pending_roll.is_empty()


func _render_pending_roll() -> void:
	var is_for_target := not _pending_roll.is_empty() and _pending_target_id == ApiClient.id_string(_selected_item.get("id"))
	pending_panel.visible = is_for_target
	if not is_for_target:
		return
	var lines: Variant = _pending_roll.get("new_lines", _pending_roll.get("choices", []))
	pending_lines.text = _format_aurora_lines(lines if lines is Array else [])
	var requires_specific_selection := _pending_roll.has("choices")
	take_new_button.disabled = requires_specific_selection or _is_loading
	take_new_button.text = "SELECT LINES — SOON" if requires_specific_selection else "TAKE NEW"
	keep_old_button.disabled = _is_loading


func _on_lumen_pressed() -> void:
	if _selected_item.is_empty() or _is_loading:
		return
	_set_loading(true, "Attempting Lumen Ascend...")
	var response: Dictionary = await ApiClient.post_json(
		"items/lumen/ascend/",
		{"inventory_item_id": int(_selected_item.get("id", 0))}
	)
	if not _accept_mutation(response):
		return
	var data: Dictionary = response.get("data", {})
	var message := str(data.get("message", "Lumen attempt completed."))
	await _play_lumen_result(str(data.get("result", "failure")), message)
	_is_loading = false
	await _load_data()
	status_label.text = message


func _play_lumen_result(result: String, message: String) -> void:
	var visual := _lumen_result_visual(result)
	var accent: Color = visual.get("accent", Color.WHITE)
	var backdrop_rgb: Color = visual.get("backdrop", Color("07101a"))
	result_symbol.text = str(visual.get("symbol", "✦"))
	result_title.text = str(visual.get("title", "LUMEN RESULT"))
	result_subtitle.text = message
	result_symbol.add_theme_color_override("font_color", accent)
	result_title.add_theme_color_override("font_color", accent)
	var card_style := StyleBoxFlat.new()
	card_style.bg_color = Color(0.035, 0.065, 0.09, 0.97)
	card_style.border_color = accent
	card_style.set_border_width_all(3)
	card_style.set_corner_radius_all(14)
	card_style.shadow_color = Color(accent, 0.35)
	card_style.shadow_size = 18
	card_style.set_content_margin_all(22)
	result_card.add_theme_stylebox_override("panel", card_style)
	result_backdrop.color = Color(backdrop_rgb, 0.0)
	result_effect_layer.visible = true
	result_card.modulate = Color(1, 1, 1, 0)
	result_card.scale = Vector2(0.72, 0.72)
	await get_tree().process_frame
	result_card.pivot_offset = result_card.size * 0.5
	_spawn_result_sparks(accent, 28 if result == "success" else (22 if result == "heavy_failure" else 10), result == "heavy_failure")

	var intro := create_tween().set_parallel(true)
	intro.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	intro.tween_property(result_card, "scale", Vector2.ONE, 0.32)
	intro.tween_property(result_card, "modulate:a", 1.0, 0.18)
	intro.tween_property(result_backdrop, "color:a", 0.72 if result == "heavy_failure" else 0.58, 0.18)
	await intro.finished

	if result == "failure":
		await _shake_result_card(7.0, 5)
	elif result == "heavy_failure":
		await _shake_result_card(18.0, 9)
		var danger_flash := create_tween()
		danger_flash.tween_property(result_backdrop, "color:a", 0.92, 0.08)
		danger_flash.tween_property(result_backdrop, "color:a", 0.62, 0.16)
		await danger_flash.finished
	else:
		var success_pulse := create_tween()
		success_pulse.tween_property(result_card, "scale", Vector2(1.06, 1.06), 0.13)
		success_pulse.tween_property(result_card, "scale", Vector2.ONE, 0.2)
		await success_pulse.finished

	await get_tree().create_timer(0.55).timeout
	var outro := create_tween().set_parallel(true)
	outro.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	outro.tween_property(result_card, "scale", Vector2(1.08, 1.08), 0.2)
	outro.tween_property(result_card, "modulate:a", 0.0, 0.2)
	outro.tween_property(result_backdrop, "color:a", 0.0, 0.24)
	await outro.finished
	result_effect_layer.visible = false
	result_card.scale = Vector2.ONE
	result_card.modulate = Color.WHITE


func _shake_result_card(strength: float, repetitions: int) -> void:
	var original_position := result_card.position
	var shake := create_tween()
	for index in range(repetitions):
		var direction := -1.0 if index % 2 == 0 else 1.0
		var remaining_strength := strength * (1.0 - float(index) / float(repetitions + 1))
		shake.tween_property(result_card, "position", original_position + Vector2(direction * remaining_strength, randf_range(-remaining_strength * 0.25, remaining_strength * 0.25)), 0.045)
	shake.tween_property(result_card, "position", original_position, 0.07)
	await shake.finished


func _spawn_result_sparks(color: Color, count: int, broken: bool) -> void:
	var center := result_effect_layer.size * 0.5
	for index in range(count):
		var spark := ColorRect.new()
		var spark_size := randf_range(4.0, 10.0) if broken else randf_range(3.0, 7.0)
		spark.size = Vector2(spark_size, spark_size)
		spark.position = center - spark.size * 0.5
		spark.pivot_offset = spark.size * 0.5
		spark.color = color.lightened(randf_range(0.0, 0.35))
		spark.mouse_filter = Control.MOUSE_FILTER_IGNORE
		result_effect_layer.add_child(spark)
		var angle := randf_range(0.0, TAU)
		var distance := randf_range(120.0, 330.0) if broken else randf_range(90.0, 250.0)
		var destination := spark.position + Vector2.from_angle(angle) * distance
		if broken:
			destination.y += randf_range(35.0, 130.0)
		var particle_tween := create_tween().set_parallel(true)
		particle_tween.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		particle_tween.tween_property(spark, "position", destination, randf_range(0.55, 0.9))
		particle_tween.tween_property(spark, "rotation", randf_range(-5.0, 5.0), randf_range(0.55, 0.9))
		particle_tween.tween_property(spark, "modulate:a", 0.0, randf_range(0.45, 0.8)).set_delay(0.12)
		particle_tween.chain().tween_callback(spark.queue_free)


func _lumen_result_visual(result: String) -> Dictionary:
	match result:
		"success":
			return {"title": "LUMEN ASCEND SUCCESS", "symbol": "✦", "accent": Color("65f0c5"), "backdrop": Color("06372f")}
		"heavy_failure":
			return {"title": "HEAVY FAILURE", "symbol": "⚠", "accent": Color("ff6675"), "backdrop": Color("4a0912")}
		_:
			return {"title": "ASCEND FAILED", "symbol": "×", "accent": Color("9aabc0"), "backdrop": Color("101927")}


func _on_reveal_pressed() -> void:
	if _selected_item.is_empty() or _is_loading:
		return
	_set_loading(true, "Revealing Aurora lines...")
	var response: Dictionary = await ApiClient.post_json(
		"items/aurora/reveal/",
		{"inventory_item_id": int(_selected_item.get("id", 0))}
	)
	await _finish_aurora_mutation(response)


func _on_reroll_pressed() -> void:
	if _selected_item.is_empty() or essence_select.selected < 0 or _is_loading:
		return
	_set_loading(true, "Applying Essence...")
	var response: Dictionary = await ApiClient.post_json(
		"items/essence/apply/",
		{
			"target_item_id": int(_selected_item.get("id", 0)),
			"modifier_item_id": int(essence_select.get_item_metadata(essence_select.selected)),
		}
	)
	if not _accept_mutation(response):
		return
	var data: Dictionary = response.get("data", {})
	if bool(data.get("pending", false)):
		_pending_roll = data
		_pending_target_id = ApiClient.id_string(_selected_item.get("id"))
	var message := str(data.get("message", "Aurora reroll completed."))
	_is_loading = false
	await _load_data()
	status_label.text = message


func _on_confirm_roll(action: String) -> void:
	if _pending_roll.is_empty() or _is_loading:
		return
	_set_loading(true, "Confirming Aurora roll...")
	var response: Dictionary = await ApiClient.post_json(
		"items/essence/confirm/",
		{"inventory_item_id": int(_pending_target_id), "action": action}
	)
	if not _accept_mutation(response):
		return
	var message := str(response.get("data", {}).get("message", "Aurora roll confirmed."))
	_pending_roll = {}
	_pending_target_id = ""
	_is_loading = false
	await _load_data()
	status_label.text = message


func _finish_aurora_mutation(response: Dictionary) -> void:
	if not _accept_mutation(response):
		return
	var message := str(response.get("data", {}).get("message", "Aurora updated."))
	_is_loading = false
	await _load_data()
	status_label.text = message


func _accept_mutation(response: Dictionary) -> bool:
	if not _accept_http(response):
		return false
	var data: Variant = response.get("data", {})
	if data is Dictionary and data.has("success") and not bool(data.get("success", false)):
		_set_loading(false, str(data.get("message", "Enhancement failed.")))
		return false
	return true


func _accept_http(response: Dictionary) -> bool:
	if response.get("ok", false):
		return true
	_set_loading(false, ApiClient.error_message(response, "Unable to update equipment."))
	return false


func _set_loading(value: bool, message: String) -> void:
	_is_loading = value
	back_button.disabled = value
	inventory_button.disabled = value
	refresh_button.disabled = value
	target_select.disabled = value
	lumen_menu_button.disabled = value
	aurora_menu_button.disabled = value
	future_menu_button.disabled = value
	status_label.text = message
	if not _selected_item.is_empty():
		_render_selected_item()


func _max_lumen_level(item: Dictionary) -> int:
	var breakdown: Variant = item.get("lumen_breakdown", {})
	if breakdown is Dictionary:
		var tier: Variant = breakdown.get("tier")
		if tier is Dictionary:
			return int(tier.get("max_level", 0))
	return 0


func _lumen_stats_text(item: Dictionary) -> String:
	var breakdown: Variant = item.get("lumen_breakdown", {})
	if not breakdown is Dictionary:
		return "No Lumen stat breakdown."
	var total: Variant = breakdown.get("total", {})
	if not total is Dictionary:
		return "No Lumen stat breakdown."
	var parts := PackedStringArray()
	for definition in [["str_boost", "STR"], ["agi_boost", "AGI"], ["int_boost", "INT"], ["att_boost", "ATT"], ["hp_boost", "HP"], ["mp_boost", "MP"]]:
		var value := int(total.get(definition[0], 0))
		if value != 0:
			parts.append("%s  +%d" % [definition[1], value])
	return "CURRENT BONUS\n%s" % ("  •  ".join(parts) if not parts.is_empty() else "No bonus yet")


func _format_aurora_lines(lines: Array) -> String:
	var result := PackedStringArray()
	for line_value in lines:
		if not line_value is Dictionary:
			continue
		var line: Dictionary = line_value
		var suffix := "%" if str(line.get("line_type", "flat")) == "percent" else ""
		result.append("◆  %s  +%s%s" % [str(line.get("stat_type", "")).to_upper(), str(line.get("value", 0)), suffix])
	return "\n".join(result) if not result.is_empty() else "No lines generated."


func _format_percent(value: Variant) -> String:
	var number := float(value)
	return str(int(number)) if is_equal_approx(number, round(number)) else ("%.2f" % number).rstrip("0").rstrip(".")


func _format_integer(value: int) -> String:
	var digits := str(absi(value))
	var formatted := ""
	while digits.length() > 3:
		formatted = "," + digits.right(3) + formatted
		digits = digits.left(digits.length() - 3)
	formatted = digits + formatted
	return "-" + formatted if value < 0 else formatted


func _find_item(item_id: String) -> Dictionary:
	for item in _items:
		if ApiClient.id_string(item.get("id")) == item_id:
			return item
	return {}


func _selected_option_id(option: OptionButton) -> String:
	if option == null or option.selected < 0:
		return ""
	return str(option.get_item_metadata(option.selected))
