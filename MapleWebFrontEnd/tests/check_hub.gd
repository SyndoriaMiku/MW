extends Node

## Hub: stamina regeneration, event text, routing of hub pages, the header from
## session/bootstrap/, switching pages, going back, the Adventure page's entry
## rules and the Settings page's sign out.

const PORT := 18771

var _server := FakeHttpServer.new()
var _posts: Array = []


func _ready() -> void:
	if not _check_stamina() or not _check_helpers() or not await _check_hub():
		return
	print("HUB_OK posts=%s" % [_posts])
	get_tree().quit(0)


func _check_stamina() -> bool:
	var start := StaminaClock.iso_to_unix("2026-10-03T08:00:00Z")
	if start != float(Time.get_unix_time_from_datetime_string("2026-10-03T08:00:00")):
		return _fail("ISO_PARSE_FAILED %s" % start)
	if StaminaClock.iso_to_unix("2026-10-03T15:00:00.500000+07:00") != start + 0.5:
		return _fail("ISO_OFFSET_FAILED")
	var clock := StaminaClock.from_character({"current_stamina": 10, "max_stamina": 12, "last_stamina_update": "2026-10-03T08:00:00Z"})
	if clock.value_at(start + 179) != 10 or clock.value_at(start + 180) != 11 or clock.value_at(start + 9999) != 12:
		return _fail("STAMINA_REGEN_FAILED")
	if clock.seconds_to_next(start + 100) != 80 or clock.seconds_to_full(start + 100) != 260:
		return _fail("STAMINA_TIMERS_FAILED %d %d" % [clock.seconds_to_next(start + 100), clock.seconds_to_full(start + 100)])
	if StaminaClock.duration_text(65) != "1:05" or StaminaClock.duration_text(11100) != "3h 05m":
		return _fail("DURATION_TEXT_FAILED")
	return true


func _check_helpers() -> bool:
	var now := StaminaClock.iso_to_unix("2026-10-03T08:00:00Z")
	var summary := HomePage.event_summary({"exp_rate_bonus": 100.0, "drop_rate_bonus": 50.0, "end_time": "2026-10-05T10:00:00Z"}, now)
	if summary != "EXP +100%  •  Drop +50%  •  Ends in 2d 2h":
		return _fail("EVENT_SUMMARY_FAILED %s" % summary)
	if HubScreen.group_digits(1234567) != "1,234,567" or HubScreen.group_digits(999) != "999":
		return _fail("GROUP_DIGITS_FAILED")
	if SceneRouter.hub_page_for(SceneRouter.INVENTORY) != "inventory" or SceneRouter.hub_page_for(SceneRouter.HUB) != "home" or SceneRouter.hub_page_for(SceneRouter.BATTLE) != "":
		return _fail("HUB_ROUTING_FAILED")
	var dungeon := {"required_level": 5, "stamina_cost": 10}
	if AdventurePage.block_reason(dungeon, 5, 10, false) != "":
		return _fail("ENTRY_ALLOWED_FAILED")
	if not AdventurePage.block_reason(dungeon, 4, 10, false).contains("level 5"):
		return _fail("ENTRY_LEVEL_RULE_FAILED")
	if not AdventurePage.block_reason(dungeon, 5, 9, false).contains("stamina"):
		return _fail("ENTRY_STAMINA_RULE_FAILED")
	if not AdventurePage.block_reason(dungeon, 9, 99, true).contains("battle"):
		return _fail("ENTRY_ACTIVE_BATTLE_RULE_FAILED")
	return true


func _check_hub() -> bool:
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		return _fail("FAKE_SERVER_LISTEN_FAILED")
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.base_url = _server.base_url(PORT)
	SessionStore.begin_session("hero_account", "token", "")
	var hub: HubScreen = load(SceneRouter.HUB).instantiate()
	add_child(hub)
	if not await _wait_for(func(): return hub.current_page() == "home"):
		return _fail("HUB_LOAD_FAILED %s" % hub.loading_label.text)
	if hub.character_name.text != "Maple Hero" or hub.lumis_label.text != "12,345" or hub.nova_label.text != "67":
		return _fail("HEADER_FAILED %s %s %s" % [hub.character_name.text, hub.lumis_label.text, hub.nova_label.text])
	if not hub.stamina_label.text.begins_with("Stamina 50/120") or not hub.stamina_hint.text.contains("full in"):
		return _fail("STAMINA_HEADER_FAILED %s / %s" % [hub.stamina_label.text, hub.stamina_hint.text])
	var home: HomePage = hub.page("home")
	if home._events_box.get_child_count() != 1:
		return _fail("HOME_EVENTS_FAILED")

	hub.nav_bar.destination_selected.emit("adventure")
	var adventure: AdventurePage = hub.page("adventure")
	if adventure == null or not await _wait_for(func(): return adventure._dungeons.size() == 3 and not adventure._busy):
		return _fail("ADVENTURE_LOAD_FAILED")
	var names := adventure._dungeons.map(func(d): return d.name)
	if names != ["Mossy Path", "Golem Ruins", "Slime Field"]:
		return _fail("ADVENTURE_ORDER_FAILED %s" % [names])
	if str(adventure._selected.get("name")) != "Mossy Path":
		return _fail("ADVENTURE_DEFAULT_PICK_FAILED %s" % adventure._selected.get("name"))
	if adventure._enter_button.disabled:
		return _fail("ADVENTURE_ENTER_DISABLED %s" % adventure._detail_reason.text)
	adventure._select(adventure._find(2))
	if not adventure._enter_button.disabled or not adventure._detail_reason.text.contains("level 10"):
		return _fail("ADVENTURE_LOCK_FAILED")

	hub.open_page("settings")
	var settings: SettingsPanel = hub.page("settings")
	await get_tree().process_frame
	if settings == null or settings.find_child("SignOutButton", true, false) == null or settings.close_button.visible:
		return _fail("SETTINGS_PAGE_FAILED")
	if hub.nav_bar.selected() != "settings":
		return _fail("NAV_SELECTION_FAILED")
	if not hub.go_back() or hub.current_page() != "adventure" or not hub.go_back() or hub.current_page() != "home":
		return _fail("BACK_FAILED %s" % hub.current_page())
	if hub.go_back():
		return _fail("BACK_PAST_START_FAILED")
	await get_tree().create_timer(M3.DURATION_MEDIUM + 0.1).timeout
	if hub.page("settings").visible or hub.page("adventure").visible or not hub.page("home").visible:
		return _fail("PAGE_VISIBILITY_FAILED")
	hub.queue_free()
	return true


func _handle(path: String, head: String, _payload: Variant) -> Array:
	if head.begins_with("POST"):
		_posts.append(path)
		return [200, {}]
	var now := Time.get_datetime_string_from_unix_time(int(Time.get_unix_time_from_system())) + "Z"
	var character := {
		"id": 7, "name": "Maple Hero", "level": 6, "current_exp": 30, "required_exp": 120,
		"current_stamina": 50, "max_stamina": 120, "last_stamina_update": now,
	}
	match path:
		"/api/session/bootstrap/":
			return [200, {
				"server_time": now,
				"profile": {"username": "hero_account", "lumis": 12345, "nova": 67},
				"character": character,
				"active_battle": null,
				"rate_events": [{"id": 1, "name": "Harvest", "exp_rate_bonus": 100.0, "end_time": null}],
			}]
		"/api/characters/my/":
			return [200, character]
		"/api/users/profile/":
			return [200, {"username": "hero_account", "lumis": 12345, "nova": 67}]
		"/api/battles/active/":
			return [200, {}]
		"/api/world/normal-dungeons/":
			return [200, {"count": 3, "next": null, "results": [
				{"id": 2, "name": "Golem Ruins", "order": 2, "required_level": 10, "stamina_cost": 12},
				{"id": 1, "name": "Slime Field", "order": 3, "required_level": 1, "stamina_cost": 6, "description": "Bouncy."},
				{"id": 3, "name": "Mossy Path", "order": 1, "required_level": 3, "stamina_cost": 8},
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
