extends Node

## Registration form checks, character name rules, DRF field errors and the
## character creation screen fed with offline data.


func _ready() -> void:
	if not _check_name_rules() or not _check_field_errors() or not await _check_register_form():
		return
	if not await _check_create_screen():
		return
	print("ONBOARDING_OK")
	get_tree().quit(0)


func _check_name_rules() -> bool:
	var cases := {
		"Adventurer1": "", "ĐứcAnh": "", "한글이름": "", "ルーキー": "", "Abcd": "",
		"Ab1": "short", "가나다라마바사": "long", "Thirteen13Abc": "long",
		"Bad Name": "symbol", "Еvil": "symbol", "Hero!": "symbol",
	}
	for name in cases:
		var problem := CharacterNameRules.validate(name)
		var expected: String = cases[name]
		var ok := problem.is_empty() if expected.is_empty() else (
			(expected == "short" and problem.begins_with("Too short"))
			or (expected == "long" and problem.begins_with("Too long"))
			or (expected == "symbol" and problem.begins_with("Only letters"))
		)
		if not ok:
			return _fail("NAME_RULE_FAILED %s -> %s" % [name, problem])
	if CharacterNameRules.width("한글이름") != 8 or CharacterNameRules.width("ĐứcAnh") != 6:
		return _fail("NAME_WIDTH_FAILED")
	return true


func _check_field_errors() -> bool:
	var error: Dictionary = ApiClient._normalize_error({"name": ["This character name is already taken."], "job": ["Required."]})
	var response := {"ok": false, "error": error}
	var fields := ApiClient.field_errors(response)
	if fields.get("name") != "This character name is already taken." or fields.get("job") != "Required.":
		return _fail("FIELD_ERRORS_FAILED %s" % error)
	if ApiClient.error_message(response, "") == "":
		return _fail("FIELD_ERROR_MESSAGE_FAILED")
	if not ApiClient.field_errors({"ok": false, "error": ApiClient._normalize_error({"detail": "Nope"})}).is_empty():
		return _fail("DETAIL_IS_NOT_FIELD_ERROR")
	# The backend's envelope carries a message as well as the fields.
	var enveloped: Dictionary = ApiClient._normalize_error({
		"password": ["This password is too common."], "code": "validation_error",
		"message": "This password is too common.", "fields": {"password": ["This password is too common."]},
	})
	if ApiClient.field_errors({"error": enveloped}).get("password") != "This password is too common." or enveloped.code != "validation_error":
		return _fail("ENVELOPE_FIELDS_FAILED %s" % enveloped)
	if ApiClient.id_string(5.0) != "5" or ApiClient.id_string("ab12") != "ab12" or ApiClient.id_string(null) != "":
		return _fail("ID_STRING_FAILED")
	return true


func _check_register_form() -> bool:
	var screen: Control = load("res://src/features/auth/presentation/register_screen.tscn").instantiate()
	add_child(screen)
	var errors: Dictionary = screen.validate_form("a b", "not-an-email", "1234567", "different")
	for field in ["username", "email", "password", "confirm"]:
		if not errors.has(field):
			return _fail("REGISTER_VALIDATION_MISSED %s" % field)
	if not screen.validate_form("player_01", "player@example.test", "12345678", "12345678").has("password"):
		return _fail("REGISTER_NUMERIC_PASSWORD_ALLOWED")
	if not screen.validate_form("player_01", "player@example.test", "maple-leaf-42", "maple-leaf-42").is_empty():
		return _fail("REGISTER_VALID_FORM_REJECTED")
	screen._show_errors({"username": "This username is already taken.", "non_field_errors": "Try again."})
	if screen.username_error.text != "This username is already taken." or screen.form_error.text != "Try again.":
		return _fail("REGISTER_SERVER_ERRORS_NOT_SHOWN")
	screen.queue_free()
	return true


func _check_create_screen() -> bool:
	# The fake server answers 503, so loading fails and the screen must stay usable with injected data.
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	var server := FakeHttpServer.new()
	add_child(server)
	if server.listen(18766) != OK:
		return _fail("FAKE_SERVER_LISTEN_FAILED")
	ApiClient.base_url = server.base_url(18766)
	SessionStore.begin_session("onboarding-test", "offline-token", "")
	var screen: Control = load("res://src/features/character/presentation/character_create_screen.tscn").instantiate()
	add_child(screen)
	var deadline := Time.get_ticks_msec() + 15000
	while not screen.retry_button.visible and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if not screen.retry_button.visible:
		return _fail("CREATE_LOAD_FAILURE_NOT_SHOWN")

	screen._classes_by_id = {
		"1": {"id": 1, "name": "Warrior", "main_stat": "str", "hp_growth": 40.0, "mp_growth": 10.0},
		"2": {"id": 2, "name": "Archer", "main_stat": "agi", "hp_growth": 20.0, "mp_growth": 20.0},
	}
	screen.set_jobs([
		{"id": 1, "name": "Paladin", "character_class": 1, "weapon_type": null, "main_stat_weight": 1.0},
		{"id": 2, "name": "Bowman", "character_class": 2, "weapon_type": "bow", "main_stat_weight": 1.0},
	])
	screen._skills_by_job["2"] = [
		{"name": "Explosive Arrow", "required_level": 2, "mp_cost": 10, "cooldown": 2, "availability": "PLAYER"},
		{"name": "Normal Attack", "required_level": 1, "is_basic_attack": true, "availability": "PLAYER"},
		{"name": "Wolf Bite", "required_level": 1, "availability": "ENEMY"},
	]
	await get_tree().process_frame
	if screen.job_list.get_child_count() != 2:
		return _fail("CREATE_JOB_BUTTONS_FAILED")
	await screen._select_job(screen._jobs[1])
	if screen.job_name.text != "Bowman" or not screen.class_line.text.contains("Archer") or not screen.job_stats.text.contains("Bow"):
		return _fail("CREATE_JOB_DETAILS_FAILED %s | %s" % [screen.class_line.text, screen.job_stats.text])
	var skill_lines: PackedStringArray = screen.skill_list.text.split("\n")
	if skill_lines.size() != 2 or not skill_lines[0].contains("Normal Attack") or screen.skill_list.text.contains("Wolf"):
		return _fail("CREATE_SKILL_LIST_FAILED %s" % screen.skill_list.text)
	if not screen.job_list.get_child(1).button_pressed or screen.job_list.get_child(0).button_pressed:
		return _fail("CREATE_JOB_SELECTION_STATE_FAILED")

	screen._set_busy(false, "")
	screen.name_input.text = "Bad Name"
	screen._on_name_changed(screen.name_input.text)
	if not screen.create_button.disabled or not screen.name_feedback.text.begins_with("Only letters"):
		return _fail("CREATE_INVALID_NAME_ALLOWED")
	screen.name_input.text = "ĐứcAnh"
	screen._on_name_changed(screen.name_input.text)
	if screen.create_button.disabled or screen.name_width.text != "6 / 12":
		return _fail("CREATE_VALID_NAME_REJECTED %s" % screen.name_width.text)
	return true


func _fail(code: String) -> bool:
	printerr(code)
	get_tree().quit(1)
	return false
