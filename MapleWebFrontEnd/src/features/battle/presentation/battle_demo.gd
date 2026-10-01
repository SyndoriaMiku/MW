extends Control

enum ScreenState {
	LOADING,
	PLAYER_INPUT,
	SUBMITTING,
	PLAYING_RESULT,
	BATTLE_ENDED,
}

@onready var connection_status: Label = %ConnectionStatus
@onready var turn_label: Label = %TurnLabel
@onready var phase_label: Label = %PhaseLabel
@onready var player_name: Label = %PlayerName
@onready var player_hp: ProgressBar = %PlayerHP
@onready var player_hp_label: Label = %PlayerHPLabel
@onready var player_mp: ProgressBar = %PlayerMP
@onready var player_mp_label: Label = %PlayerMPLabel
@onready var enemy_name: Label = %EnemyName
@onready var enemy_hp: ProgressBar = %EnemyHP
@onready var enemy_hp_label: Label = %EnemyHPLabel
@onready var combat_log: RichTextLabel = %CombatLog
@onready var back_button: Button = %BackButton
@onready var attack_button: Button = %AttackButton
@onready var skill_button: Button = %SkillButton
@onready var retry_button: Button = %RetryButton

var _repository := BattleRepository.new()
var _battle: BattleState
var _screen_state := ScreenState.LOADING
var _combat_id: String = "demo-1v1"
var _skill_popup: PopupPanel
var _skill_list: VBoxContainer


func _ready() -> void:
	_setup_skill_popup()
	attack_button.pressed.connect(_on_attack_pressed)
	skill_button.pressed.connect(_on_skill_button_pressed)
	back_button.pressed.connect(_on_back_pressed)
	retry_button.pressed.connect(_on_retry_pressed)
	if not SessionStore.active_battle_id.is_empty():
		_combat_id = SessionStore.active_battle_id
		_repository.use_mock = false
	_append_log("Preparing the battle...")
	await _load_battle()


func _load_battle() -> void:
	_set_screen_state(ScreenState.LOADING)
	var response: Dictionary = await _repository.load_battle(_combat_id)
	if not response.get("ok", false):
		_show_error(response.get("error", {}))
		return
	_battle = BattleState.from_dict(response.data)
	_render_battle()
	var enemy := _battle.first_enemy()
	_append_log("A wild %s appeared." % (enemy.display_name if enemy != null else "enemy"))
	_set_screen_state(ScreenState.PLAYER_INPUT)


func _on_attack_pressed() -> void:
	if _battle == null or not _battle.can_local_player_act():
		return
	var enemy := _battle.first_enemy()
	if enemy == null or not enemy.is_alive():
		return

	_set_screen_state(ScreenState.SUBMITTING)
	var response: Dictionary = await _repository.submit_attack(_combat_id, enemy)
	await _resolve_action_response(response)


func _on_skill_button_pressed() -> void:
	if _skill_popup.visible:
		_skill_popup.hide()
		return
	if _battle == null or not _battle.can_local_player_act():
		return
	_render_skill_list()
	var skills := _selectable_skills()
	var popup_height := mini(380, 54 + maxi(1, skills.size()) * 70)
	var button_position := skill_button.get_screen_position()
	var popup_position := Vector2i(
		int(button_position.x),
		maxi(10, int(button_position.y) - popup_height - 8)
	)
	_skill_popup.popup(Rect2i(popup_position, Vector2i(370, popup_height)))


func _on_skill_selected(skill: Dictionary) -> void:
	if not bool(skill.get("can_use", false)) or _battle == null:
		return
	_skill_popup.hide()
	var target := _target_for_skill(skill)
	if target == null and str(skill.get("target_type", "ENEMY")) in ["ENEMY", "ALLY", "SELF"]:
		return
	_set_screen_state(ScreenState.SUBMITTING)
	var response: Dictionary = await _repository.submit_skill(_combat_id, skill, target)
	await _resolve_action_response(response)


func _resolve_action_response(response: Dictionary) -> void:
	if not response.get("ok", false):
		_show_error(response.get("error", {}))
		return

	_set_screen_state(ScreenState.PLAYING_RESULT)
	for event in response.data.get("events", []):
		_present_event(event)
		await get_tree().create_timer(0.35).timeout

	_battle = BattleState.from_dict(response.data.combat)
	_render_battle()
	if _battle.status == "in_progress":
		_set_screen_state(ScreenState.PLAYER_INPUT)
	else:
		_set_screen_state(ScreenState.BATTLE_ENDED)


func _setup_skill_popup() -> void:
	_skill_popup = PopupPanel.new()
	_skill_popup.name = "SkillPopup"
	_skill_popup.unresizable = true
	var popup_style := StyleBoxFlat.new()
	popup_style.bg_color = Color("101824")
	popup_style.border_color = Color("3a5875")
	popup_style.set_border_width_all(2)
	popup_style.set_corner_radius_all(10)
	_skill_popup.add_theme_stylebox_override("panel", popup_style)
	add_child(_skill_popup)

	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_top", 12)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_bottom", 12)
	_skill_popup.add_child(margin)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 8)
	margin.add_child(root)
	var title := Label.new()
	title.text = "SELECT SKILL"
	title.add_theme_color_override("font_color", Color("66c9f5"))
	title.add_theme_font_size_override("font_size", 14)
	root.add_child(title)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	root.add_child(scroll)
	_skill_list = VBoxContainer.new()
	_skill_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_skill_list.add_theme_constant_override("separation", 7)
	scroll.add_child(_skill_list)


func _render_skill_list() -> void:
	for child in _skill_list.get_children():
		child.free()
	var skills := _selectable_skills()
	if skills.is_empty():
		var empty := Label.new()
		empty.text = "No job skills available."
		empty.add_theme_color_override("font_color", Color("7f8d9d"))
		_skill_list.add_child(empty)
		return
	for skill_value in skills:
		if not skill_value is Dictionary:
			continue
		var skill: Dictionary = skill_value
		var button := Button.new()
		button.custom_minimum_size = Vector2(330, 60)
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.text = _skill_button_text(skill)
		button.tooltip_text = _skill_tooltip_text(skill)
		button.disabled = not bool(skill.get("can_use", false))
		button.add_theme_font_size_override("font_size", 13)
		var normal_style := StyleBoxFlat.new()
		normal_style.bg_color = Color("18334d")
		normal_style.border_color = Color("3977a6")
		normal_style.set_border_width_all(1)
		normal_style.set_corner_radius_all(7)
		normal_style.set_content_margin_all(9)
		button.add_theme_stylebox_override("normal", normal_style)
		var hover_style := normal_style.duplicate()
		hover_style.bg_color = Color("22527a")
		button.add_theme_stylebox_override("hover", hover_style)
		var disabled_style := normal_style.duplicate()
		disabled_style.bg_color = Color("242a32")
		disabled_style.border_color = Color("454d57")
		button.add_theme_stylebox_override("disabled", disabled_style)
		button.add_theme_color_override("font_disabled_color", Color("7d858f"))
		button.pressed.connect(_on_skill_selected.bind(skill))
		_skill_list.add_child(button)


func _selectable_skills() -> Array:
	if _battle == null:
		return []
	var player := _battle.player()
	if player == null:
		return []
	var result: Array = []
	for skill_value in player.skills:
		if skill_value is Dictionary and not bool(skill_value.get("is_basic_attack", false)):
			result.append(skill_value)
	return result


func _skill_button_text(skill: Dictionary) -> String:
	var cooldown_remaining := int(skill.get("cooldown_remaining", 0))
	var status := ""
	if cooldown_remaining > 0:
		status = "  •  CD %d TURN%s" % [cooldown_remaining, "" if cooldown_remaining == 1 else "S"]
	elif not bool(skill.get("can_use", false)):
		status = "  •  NOT ENOUGH MP"
	return "%s  Lv.%d%s\nMP %d  •  %s  •  Damage ×%.2f" % [
		str(skill.get("name", "Unknown Skill")),
		int(skill.get("level", 1)),
		status,
		int(skill.get("mp_cost", 0)),
		str(skill.get("target_type", "ENEMY")).replace("_", " "),
		float(skill.get("damage_multiplier", 1.0)),
	]


func _skill_tooltip_text(skill: Dictionary) -> String:
	return "Cooldown %d turns  •  %s" % [
		int(skill.get("cooldown", 0)),
		str(skill.get("effect_type", "DAMAGE")).capitalize(),
	]


func _target_for_skill(skill: Dictionary) -> CombatantState:
	var target_type := str(skill.get("target_type", "ENEMY"))
	if target_type in ["SELF", "ALLY"]:
		return _battle.player()
	if target_type == "ENEMY":
		return _battle.first_enemy()
	return null


func _on_retry_pressed() -> void:
	if not _repository.use_mock:
		SessionStore.active_battle_id = ""
		SceneRouter.go_to(SceneRouter.LAUNCHER)
		return
	_repository.reset_mock()
	combat_log.clear()
	await _load_battle()


func _on_back_pressed() -> void:
	if _battle != null and _battle.status != "in_progress":
		SessionStore.active_battle_id = ""
	SceneRouter.go_to(SceneRouter.LAUNCHER)


func _present_event(event: Dictionary) -> void:
	match str(event.get("type", "")):
		"damage_applied":
			_append_log(
				"%s dealt %d damage to %s."
				% [event.get("actor_name", "Unknown"), event.get("amount", 0), event.get("target_name", "Unknown")]
			)
		"combatant_defeated":
			_append_log("%s was defeated." % event.get("target_name", "Unknown"))
		"turn_started":
			_append_log("Turn %d begins." % event.get("turn", 1))
		"battle_victory":
			_append_log("Victory!", Color("73e2a7"))
		"battle_defeat":
			_append_log("Defeat.", Color("ff7b72"))
		"combat_message":
			_append_log(str(event.get("message", "The action was resolved.")))
		_:
			if event.has("message") and not str(event.get("message", "")).is_empty():
				_append_log(str(event.message))


func _render_battle() -> void:
	var player := _battle.player()
	var enemy := _battle.first_enemy()
	if player != null:
		player_name.text = player.display_name
		player_hp.max_value = player.max_hp
		player_hp.value = player.current_hp
		player_hp_label.text = "HP  %d / %d" % [player.current_hp, player.max_hp]
		player_mp.max_value = player.max_mp
		player_mp.value = player.current_mp
		player_mp_label.text = "MP  %d / %d" % [player.current_mp, player.max_mp]
	if enemy != null:
		enemy_name.text = enemy.display_name
		enemy_hp.max_value = enemy.max_hp
		enemy_hp.value = enemy.current_hp
		enemy_hp_label.text = "HP  %d / %d" % [enemy.current_hp, enemy.max_hp]
	turn_label.text = "TURN %02d" % _battle.turn_count
	phase_label.text = _status_text()
	if _skill_popup != null and _skill_popup.visible:
		_render_skill_list()


func _set_screen_state(next_state: ScreenState) -> void:
	_screen_state = next_state
	attack_button.disabled = next_state != ScreenState.PLAYER_INPUT
	var has_job_skills := not _selectable_skills().is_empty()
	skill_button.disabled = next_state != ScreenState.PLAYER_INPUT or not has_job_skills
	if next_state != ScreenState.PLAYER_INPUT and _skill_popup != null:
		_skill_popup.hide()
	retry_button.visible = next_state == ScreenState.BATTLE_ENDED
	match next_state:
		ScreenState.LOADING:
			connection_status.text = "LOADING"
		ScreenState.SUBMITTING:
			connection_status.text = "SENDING ACTION"
		ScreenState.PLAYING_RESULT:
			connection_status.text = "RESOLVING TURN"
		ScreenState.BATTLE_ENDED:
			connection_status.text = "BATTLE COMPLETE"
		_:
			connection_status.text = "MOCK SERVER" if _repository.use_mock else "LIVE SERVER"


func _status_text() -> String:
	match _battle.status:
		"victory":
			return "VICTORY"
		"defeat":
			return "DEFEAT"
		_:
			return "PLAYER PHASE"


func _show_error(error: Dictionary) -> void:
	_append_log(str(error.get("message", "Unexpected error.")), Color("ff7b72"))
	_set_screen_state(ScreenState.BATTLE_ENDED)
	connection_status.text = str(error.get("code", "ERROR"))


func _append_log(message: String, color: Color = Color("c8d4e3")) -> void:
	combat_log.push_color(color)
	combat_log.append_text("• %s\n" % message)
	combat_log.pop()
	combat_log.scroll_to_line(maxi(0, combat_log.get_line_count() - 1))
