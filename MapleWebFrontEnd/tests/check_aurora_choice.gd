extends Node

## The Aurora choice blocks until the player decides, a tier-up roll can only
## be taken, triple choices need the exact number of lines, and the
## enhancement screen reopens a roll the server still has pending.

const PORT := 18768

var _server := FakeHttpServer.new()
var _confirms: Array = []
var _refuse_next_confirm := true


func _ready() -> void:
	if not await _check_panel() or not await _check_screen():
		return
	print("AURORA_CHOICE_OK confirms=%s" % [_confirms])
	get_tree().quit(0)


func _item(pending: Variant) -> Dictionary:
	return {
		"id": 21, "aurora_level": 1, "lumen_ascend_level": 0, "quantity": 1,
		"aurora_lines": [{"line_index": 0, "stat_type": "att", "line_type": "percent", "value": 1.0}],
		"template": {"id": 1, "name": "Copper Hammer", "item_type": "weapon", "aurora_tier": 1, "lumen_tier": null},
		"pending_aurora_roll": pending,
	}


func _check_panel() -> bool:
	var panel: AuroraChoicePanel = load("res://src/features/enhancement/presentation/aurora_choice_panel.tscn").instantiate()
	add_child(panel)
	var decisions: Array = []
	panel.decided.connect(func(action, ids): decisions.append([action, ids]))

	panel.show_roll(_item({
		"modifier_type": "REROLL_CHOICE", "current_aurora_level": 1, "new_aurora_level": 1,
		"must_take_new": false, "new_lines": [{"line_index": 0, "stat_type": "str", "line_type": "flat", "value": 6.0}],
	}))
	if not panel.visible or panel.keep_button.disabled or panel.take_button.disabled or panel.new_lines.get_child_count() != 1:
		return _fail("CHOICE_PANEL_FAILED")
	var escape := InputEventAction.new()
	escape.action = "ui_cancel"
	escape.pressed = true
	Input.parse_input_event(escape)
	await get_tree().process_frame
	if not panel.visible:
		return _fail("ESCAPE_CLOSED_THE_CHOICE")
	panel.keep_button.pressed.emit()
	if decisions != [["keep_old", []]] or not panel.keep_button.disabled:
		return _fail("KEEP_DECISION_FAILED %s" % [decisions])

	panel.show_roll(_item({
		"modifier_type": "REROLL_CHOICE", "current_aurora_level": 1, "new_aurora_level": 2,
		"tier_up": true, "must_take_new": true, "new_lines": [{"line_index": 0, "stat_type": "att", "line_type": "percent", "value": 4.0}],
	}))
	if not panel.keep_button.disabled or panel.title_label.text != "AURORA TIER UP!" or not panel.subtitle_label.text.contains("1  →  2"):
		return _fail("TIER_UP_NOT_FORCED")
	panel._decide("keep_old")
	if decisions.size() != 1:
		return _fail("TIER_UP_KEEP_ALLOWED")

	var choices: Array = []
	for index in 6:
		choices.append({"temp_id": index, "line_index": index % 2, "stat_type": "agi", "line_type": "flat", "value": index + 1})
	panel.show_roll(_item({
		"modifier_type": "REROLL_TRIPLE_CHOICE", "current_aurora_level": 1, "new_aurora_level": 1,
		"must_take_new": false, "select_count": 2, "choices": choices,
	}))
	if panel.new_lines.get_child_count() != 6 or not panel.take_button.disabled:
		return _fail("TRIPLE_CHOICE_RENDER_FAILED")
	panel.toggle_choice(4)
	panel.toggle_choice(1)
	panel.toggle_choice(5)
	if panel.take_button.disabled or not panel.take_button.text.contains("2/2") or panel.new_lines.get_child(5).button_pressed:
		return _fail("TRIPLE_CHOICE_SELECTION_FAILED")
	panel.take_button.pressed.emit()
	if decisions[-1] != ["select_specific", [4, 1]]:
		return _fail("TRIPLE_CHOICE_DECISION_FAILED %s" % [decisions])
	panel.queue_free()
	return true


func _check_screen() -> bool:
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		return _fail("FAKE_SERVER_LISTEN_FAILED")
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.base_url = _server.base_url(PORT)
	SessionStore.begin_session("enhancer", "token", "")
	var screen: Control = load("res://src/features/enhancement/presentation/enhancement_screen.tscn").instantiate()
	add_child(screen)
	var panel: AuroraChoicePanel = screen.aurora_choice_panel
	if not await _wait_for(func(): return panel.visible):
		return _fail("PENDING_ROLL_NOT_REOPENED")
	if not panel.keep_button.disabled or screen.system_pages.current_tab != 1:
		return _fail("SCREEN_TIER_UP_STATE_FAILED")

	# The server refuses once: the choice stays open with the error.
	panel.take_button.pressed.emit()
	if not await _wait_for(func(): return not panel.error_label.text.is_empty()) or not panel.visible:
		return _fail("CONFIRM_ERROR_NOT_SHOWN")
	panel.take_button.pressed.emit()
	if not await _wait_for(func(): return not panel.visible and not screen._is_loading):
		return _fail("CHOICE_NOT_CLOSED_AFTER_CONFIRM")
	if _confirms != ["take_new", "take_new"]:
		return _fail("CONFIRM_REQUESTS_FAILED %s" % [_confirms])
	screen.queue_free()
	return true


func _handle(path: String, _head: String, payload: Variant) -> Array:
	if path == "/api/users/profile/":
		return [200, {"lumis": 100}]
	if path == "/api/inventory/":
		var pending: Variant = null
		if _confirms.size() < 2:
			pending = {
				"modifier_type": "REROLL_CHOICE", "current_aurora_level": 1, "new_aurora_level": 2,
				"tier_up": true, "must_take_new": true,
				"new_lines": [{"line_index": 0, "stat_type": "att", "line_type": "percent", "value": 4.0}],
			}
		return [200, {"count": 1, "next": null, "results": [_item(pending)]}]
	if path == "/api/items/essence/confirm/":
		_confirms.append(payload.get("action"))
		if _refuse_next_confirm:
			_refuse_next_confirm = false
			return [400, {"success": false, "message": "Try again.", "code": "bad_request", "fields": {}}]
		return [200, {"success": true, "message": "New lines applied."}]
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
