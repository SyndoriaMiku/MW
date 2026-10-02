extends Control

## Turn-based battle against the backend, or against MockBattleServer when the
## scene runs without an active battle (F6). The server resolves the whole round,
## monster phase included, in one action response; this screen replays its
## events, then applies the returned snapshot.

enum ScreenState {
	LOADING,
	PLAYER_INPUT,
	WAITING,
	SUBMITTING,
	PLAYING_RESULT,
	BATTLE_ENDED,
}

## Pause between replayed events; tests shorten it.
var event_delay := 0.45
const TARGET_TYPE_LABELS := {
	"SELF": "Self", "ALLY": "One ally", "ENEMY": "One enemy",
	"E_AREA": "All enemies", "A_AREA": "All allies", "GLOBAL": "Everyone",
}
const HIT_COLORS := {
	"damage": Color("ff6b6b"), "heal": Color("73e2a7"), "mp": Color("6fa8ff"), "blocked": Color("c8d4e3"),
}
const LOG_COLOR := Color("c8d4e3")
const ERROR_COLOR := Color("ff7b72")

@onready var encounter_label: Label = %EncounterLabel
@onready var turn_label: Label = %TurnLabel
@onready var phase_label: Label = %PhaseLabel
@onready var connection_status: Label = %ConnectionStatus
@onready var forfeit_button: Button = %ForfeitButton
@onready var back_button: Button = %BackButton
@onready var party_list: VBoxContainer = %PartyList
@onready var enemy_grid: GridContainer = %EnemyGrid
@onready var combat_log: RichTextLabel = %CombatLog
@onready var target_label: Label = %TargetLabel
@onready var attack_button: Button = %AttackButton
@onready var skill_button: Button = %SkillButton
@onready var item_button: Button = %ItemButton
@onready var hint_label: Label = %HintLabel
@onready var skip_idle_button: Button = %SkipIdleButton
@onready var effect_layer: Control = %EffectLayer
@onready var result_overlay: Control = %ResultOverlay
@onready var result_title: Label = %ResultTitle
@onready var result_subtitle: Label = %ResultSubtitle
@onready var rewards_label: Label = %RewardsLabel
@onready var result_error: Label = %ResultError
@onready var again_button: Button = %AgainButton
@onready var board_button: Button = %BoardButton
@onready var forfeit_dialog: ConfirmationDialog = %ForfeitDialog
@onready var poll_timer: Timer = %PollTimer

var _repository := BattleRepository.new()
var _battle: BattleState
var _screen_state := ScreenState.LOADING
var _combat_id := ""
var _local_entity_id := ""
var _target_enemy_id := 0
var _target_ally_id := 0
var _last_result: Dictionary = {}
var _cards: Dictionary = {}
var _choice_popup: PopupPanel
var _choice_title: Label
var _choice_list: VBoxContainer


func _ready() -> void:
	_setup_choice_popup()
	attack_button.pressed.connect(_on_attack_pressed)
	skill_button.pressed.connect(_on_skill_button_pressed)
	item_button.pressed.connect(_on_item_button_pressed)
	forfeit_button.pressed.connect(_on_forfeit_pressed)
	forfeit_dialog.confirmed.connect(_on_forfeit_confirmed)
	back_button.pressed.connect(_leave_to_board)
	board_button.pressed.connect(_leave_to_board)
	again_button.pressed.connect(_on_again_pressed)
	skip_idle_button.pressed.connect(_on_skip_idle_pressed)
	poll_timer.timeout.connect(_poll)
	party_list.get_parent().resized.connect(_fit_cards)
	if not SessionStore.active_battle_id.is_empty():
		_combat_id = SessionStore.active_battle_id
		_repository.use_mock = false
		_local_entity_id = ApiClient.id_string(SessionStore.character.get("id"))
	_append_log("Preparing the battle...")
	await _load_battle()


func _load_battle() -> void:
	_set_screen_state(ScreenState.LOADING)
	var response: Dictionary = await _repository.load_battle(_combat_id)
	if not response.get("ok", false):
		_append_log(ApiClient.error_message(response, "Unable to load the battle."), ERROR_COLOR)
		connection_status.text = str(response.get("error", {}).get("code", "ERROR")).to_upper()
		hint_label.text = "Go back to the board and try again."
		back_button.disabled = false
		return
	var is_first_load := _battle == null
	_apply_state(BattleState.from_dict(response.get("data", {}), _local_entity_id))
	if is_first_load:
		var names := PackedStringArray()
		for enemy in _battle.enemies():
			if enemy.is_alive():
				names.append(enemy.display_name)
		if not names.is_empty():
			_append_log("Enemies appear: %s." % ", ".join(names))


func _apply_state(battle: BattleState) -> void:
	var previous_turn := _battle.turn_count if _battle != null else 0
	_battle = battle
	_render_field()
	if previous_turn > 0 and battle.turn_count > previous_turn and battle.is_in_progress():
		_append_log("Turn %d begins." % battle.turn_count)
	if not battle.is_in_progress():
		_set_screen_state(ScreenState.BATTLE_ENDED)
		_show_result()
	elif battle.can_local_player_act():
		_set_screen_state(ScreenState.PLAYER_INPUT)
	else:
		_set_screen_state(ScreenState.WAITING)


func _render_field() -> void:
	var encounter_name: Variant = _battle.encounter.get("name")
	encounter_label.text = str(encounter_name).to_upper() if encounter_name != null and str(encounter_name) != "" else "BATTLE"
	turn_label.text = "TURN %02d" % _battle.turn_count
	phase_label.text = _phase_text()

	_cards.clear()
	for container in [party_list, enemy_grid]:
		for child in container.get_children():
			child.queue_free()
	var local_player := _battle.player()
	var actor := _battle.current_actor()
	for combatant in _battle.players():
		party_list.add_child(_create_card(combatant, combatant == local_player, combatant == actor))
	var enemies := _battle.enemies()
	enemy_grid.columns = clampi(enemies.size(), 1, 3)
	for combatant in enemies:
		enemy_grid.add_child(_create_card(combatant, false, false))
	_fit_cards.call_deferred()
	_ensure_targets()
	_render_targets()


## Splits the arena height between the rows of cards so few cards get big portraits.
func _fit_cards() -> void:
	var column: Control = party_list.get_parent()
	var available := column.size.y - party_list.position.y
	if available <= 0.0 or _battle == null:
		return
	var party_size := maxi(1, _battle.players().size())
	var enemy_rows := ceili(_battle.enemies().size() / 3.0)
	for card in party_list.get_children():
		if card is CombatantCard and not card.is_queued_for_deletion():
			card.set_card_height(clampf(available / party_size - 8.0, 150.0, 260.0))
	for card in enemy_grid.get_children():
		if card is CombatantCard and not card.is_queued_for_deletion():
			card.set_card_height(clampf(available / maxi(1, enemy_rows) - 12.0, 180.0, 420.0))


func _create_card(combatant: CombatantState, is_local: bool, has_turn: bool) -> CombatantCard:
	var card := CombatantCard.new(combatant.is_player)
	if not combatant.is_player:
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.bind(combatant, is_local, has_turn)
	card.pressed.connect(_on_card_pressed)
	_cards[combatant.id] = card
	return card


## Keeps the enemy and ally targets on living combatants.
func _ensure_targets() -> void:
	var enemy := _battle.combatant_by_id(_target_enemy_id)
	if enemy == null or enemy.is_player or not enemy.is_alive():
		var first := _battle.first_enemy()
		_target_enemy_id = first.id if first != null and first.is_alive() else 0
	var ally := _battle.combatant_by_id(_target_ally_id)
	if ally == null or not ally.is_player or not ally.is_alive():
		var local_player := _battle.player()
		_target_ally_id = local_player.id if local_player != null else 0


func _on_card_pressed(combatant_id: int) -> void:
	if _battle == null or not _battle.is_in_progress():
		return
	var combatant := _battle.combatant_by_id(combatant_id)
	if combatant == null or not combatant.is_alive():
		return
	if combatant.is_player:
		_target_ally_id = combatant_id
	else:
		_target_enemy_id = combatant_id
	_render_targets()


func _render_targets() -> void:
	var show_ally := _battle.players().size() > 1
	for combatant_id in _cards:
		_cards[combatant_id].set_selected(combatant_id == _target_enemy_id or (show_ally and combatant_id == _target_ally_id))
	var enemy := _battle.combatant_by_id(_target_enemy_id)
	var text := "TARGET  %s" % (enemy.display_name if enemy != null else "—")
	var ally := _battle.combatant_by_id(_target_ally_id)
	if show_ally and ally != null:
		text += "     ALLY  %s" % ally.display_name
	target_label.text = text


func _on_attack_pressed() -> void:
	var target := _battle.combatant_by_id(_target_enemy_id) if _battle != null else null
	if target == null:
		return
	await _submit(BattleRepository.attack_payload(target))


func _on_skill_button_pressed() -> void:
	var local_player := _battle.player() if _battle != null else null
	if local_player == null:
		return
	var entries: Array = []
	for skill in local_player.job_skills():
		entries.append({
			"text": skill_entry_text(skill),
			"tooltip": "Cooldown %d turns  •  %s" % [int(skill.get("cooldown", 0)), str(skill.get("effect_type", "DAMAGE")).capitalize()],
			"disabled": not bool(skill.get("can_use", false)),
			"pick": _use_skill.bind(skill),
		})
	_open_choices("SELECT SKILL", entries, skill_button, "No job skills available.")


func _use_skill(skill: Dictionary) -> void:
	var target: CombatantState = null
	match str(skill.get("target_type", "ENEMY")):
		"ENEMY":
			target = _battle.combatant_by_id(_target_enemy_id)
			if target == null:
				return
		"ALLY":
			target = _battle.combatant_by_id(_target_ally_id)
	await _submit(BattleRepository.skill_payload(skill, target))


func _on_item_button_pressed() -> void:
	var local_player := _battle.player() if _battle != null else null
	if local_player == null:
		return
	var entries: Array = []
	for item in local_player.consumables:
		if item is Dictionary:
			entries.append({
				"text": item_entry_text(item),
				"tooltip": "Using an item takes your turn.",
				"disabled": not bool(item.get("can_use", false)),
				"pick": _use_item.bind(item),
			})
	_open_choices("USE ITEM", entries, item_button, "No battle items in your inventory.")


func _use_item(item: Dictionary) -> void:
	var target := _battle.player()
	if str(item.get("target_type", "SELF")) == "ALLY":
		target = _battle.combatant_by_id(_target_ally_id)
	await _submit(BattleRepository.item_payload(item, target))


func _submit(payload: Dictionary) -> void:
	if _battle == null or _screen_state != ScreenState.PLAYER_INPUT or not _battle.can_local_player_act():
		return
	_set_screen_state(ScreenState.SUBMITTING)
	var response: Dictionary = await _repository.submit_action(_battle, payload)
	await _handle_battle_response(response)


func _handle_battle_response(response: Dictionary) -> void:
	if not response.get("ok", false):
		_append_log(ApiClient.error_message(response, "The action failed."), ERROR_COLOR)
		if str(response.get("error", {}).get("code", "")) == "VERSION_CONFLICT":
			await _load_battle()
		elif _battle != null:
			_apply_state(_battle)
		return
	var data: Dictionary = response.get("data", {})
	var events: Array = data.get("events", [])
	await _play_events(events)
	var result := BattleEvents.battle_result(events)
	if not result.is_empty():
		_last_result = result
	var combat: Variant = data.get("combat", {})
	if combat is Dictionary and not combat.is_empty():
		_apply_state(BattleState.from_dict(combat, _local_entity_id))
	else:
		await _load_battle()


func _play_events(events: Array) -> void:
	_set_screen_state(ScreenState.PLAYING_RESULT)
	for event in events:
		if not event is Dictionary:
			continue
		for line in BattleEvents.log_lines(event):
			_append_log(line.text, line.color)
		for hit in BattleEvents.hits(event):
			_show_hit(hit)
		await get_tree().create_timer(event_delay).timeout


func _show_hit(hit: Dictionary) -> void:
	var card: CombatantCard = _cards.get(int(hit.target_id))
	if card == null:
		return
	card.apply_hit(str(hit.kind), int(hit.amount))
	var label := Label.new()
	label.text = hit_text(hit)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.custom_minimum_size = Vector2(160, 0)
	label.add_theme_font_size_override("font_size", 28)
	label.add_theme_color_override("font_color", HIT_COLORS.get(str(hit.kind), Color.WHITE))
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	label.add_theme_constant_override("outline_size", 6)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	effect_layer.add_child(label)
	label.position = card.global_position - effect_layer.global_position + Vector2(card.size.x / 2.0 - 80.0, card.size.y * 0.35)
	var tween := label.create_tween()
	tween.tween_property(label, "position:y", label.position.y - 56.0, 0.8).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 0.8).set_delay(0.3)
	tween.tween_callback(label.queue_free)


static func hit_text(hit: Dictionary) -> String:
	var amount := int(hit.get("amount", 0))
	match str(hit.get("kind", "")):
		"heal":
			return "+%d" % amount
		"mp":
			return "+%d MP" % amount
		"blocked":
			return "BLOCKED %d" % amount
	return "-%d" % amount


static func skill_entry_text(skill: Dictionary) -> String:
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
		TARGET_TYPE_LABELS.get(str(skill.get("target_type", "ENEMY")), str(skill.get("target_type", ""))),
		float(skill.get("damage_multiplier", 1.0)),
	]


static func item_entry_text(item: Dictionary) -> String:
	var cooldown_remaining := int(item.get("cooldown_remaining", 0))
	var parts := PackedStringArray()
	if int(item.get("hp_restore", 0)) > 0:
		parts.append("+%d HP" % int(item.hp_restore))
	if float(item.get("hp_restore_percent", 0.0)) > 0.0:
		parts.append("+%d%% HP" % roundi(float(item.hp_restore_percent) * 100.0))
	if int(item.get("mp_restore", 0)) > 0:
		parts.append("+%d MP" % int(item.mp_restore))
	if float(item.get("mp_restore_percent", 0.0)) > 0.0:
		parts.append("+%d%% MP" % roundi(float(item.mp_restore_percent) * 100.0))
	if item.get("effect") != null:
		parts.append(str(item.effect))
	return "%s  ×%d%s\n%s" % [
		str(item.get("name", "Item")),
		int(item.get("quantity", 0)),
		"  •  CD %d" % cooldown_remaining if cooldown_remaining > 0 else "",
		"  •  ".join(parts) if not parts.is_empty() else "No effect listed",
	]


func _on_forfeit_pressed() -> void:
	if _battle != null and _battle.is_in_progress():
		forfeit_dialog.popup_centered()


func _on_forfeit_confirmed() -> void:
	if _battle == null or not _battle.is_in_progress() or _screen_state in [ScreenState.SUBMITTING, ScreenState.PLAYING_RESULT]:
		return
	_set_screen_state(ScreenState.SUBMITTING)
	var response: Dictionary = await _repository.forfeit(_battle.id)
	await _handle_battle_response(response)


func _on_skip_idle_pressed() -> void:
	if _battle == null or _screen_state != ScreenState.WAITING:
		return
	_set_screen_state(ScreenState.SUBMITTING)
	var response: Dictionary = await _repository.skip_idle_turn(_battle.id)
	await _handle_battle_response(response)


## In a party battle another player may be acting; refresh until the turn comes back.
func _poll() -> void:
	if _screen_state != ScreenState.WAITING or _battle == null:
		return
	var response: Dictionary = await _repository.load_battle(_battle.id)
	if _screen_state != ScreenState.WAITING or not response.get("ok", false):
		return
	var latest := BattleState.from_dict(response.get("data", {}), _local_entity_id)
	if latest.version != _battle.version:
		_append_log("The battle moved on.")
		_apply_state(latest)


func _show_result() -> void:
	result_overlay.visible = true
	result_error.text = ""
	var victory := _battle.status == "victory"
	result_title.text = "VICTORY" if victory else "DEFEAT"
	result_title.add_theme_color_override("font_color", BattleEvents.COLOR_VICTORY if victory else BattleEvents.COLOR_DEFEAT)
	result_subtitle.text = encounter_label.text
	var local_player := _battle.player()
	rewards_label.text = result_summary(
		victory,
		_last_result,
		local_player.display_name if local_player != null else "",
		local_player != null and local_player.has_left,
		_battle.encounter.get("type") == "normal_dungeon",
	)
	var can_retry: bool = _repository.use_mock or _battle.encounter.get("type") == "normal_dungeon"
	again_button.visible = can_retry
	again_button.disabled = false
	again_button.text = "PLAY AGAIN" if _repository.use_mock else "ENTER AGAIN"


static func result_summary(victory: bool, result: Dictionary, character_name: String, has_left: bool, is_normal_dungeon: bool) -> String:
	if not victory:
		var reason := "You left the battle." if has_left else "Your party was defeated."
		return reason + ("\nNo stamina was spent." if is_normal_dungeon else "")
	var rewards := BattleEvents.rewards_for(result, character_name)
	if rewards.is_empty():
		return "Rewards were granted when the battle ended."
	var lines := PackedStringArray([
		"EXP  +%d" % int(rewards.get("exp_gained", 0)),
		"LUMIS  +%d" % int(rewards.get("lumis_gained", 0)),
	])
	if bool(rewards.get("level_up", false)):
		lines.append("LEVEL UP!")
	var drops := PackedStringArray()
	for drop in rewards.get("items_dropped", []):
		if drop is Dictionary:
			drops.append("%s ×%d" % [str(drop.get("name", "Item")), int(drop.get("qty", 1))])
	lines.append("Drops: %s" % ", ".join(drops) if not drops.is_empty() else "No item drops")
	var party_loot: Variant = result.get("rewards", {}).get("party_loot") if result.get("rewards") is Dictionary else null
	if party_loot is Array and not party_loot.is_empty():
		lines.append("Party loot waits for the leader to share it.")
	return "\n".join(lines)


func _on_again_pressed() -> void:
	again_button.disabled = true
	result_error.text = ""
	if _repository.use_mock:
		_repository.reset_mock()
		result_overlay.visible = false
		combat_log.clear()
		_battle = null
		_last_result = {}
		await _load_battle()
		return
	var response: Dictionary = await _repository.enter_normal_dungeon(int(_battle.encounter.get("id", 0)))
	if not response.get("ok", false):
		result_error.text = ApiClient.error_message(response, "Unable to enter the dungeon.")
		again_button.disabled = false
		return
	SessionStore.active_battle_id = ApiClient.id_string(response.get("data", {}).get("combat_instance_id"))
	SceneRouter.go_to(SceneRouter.BATTLE)


func _leave_to_board() -> void:
	if _battle == null or not _battle.is_in_progress():
		SessionStore.active_battle_id = ""
	SceneRouter.go_to(SceneRouter.LAUNCHER)


func _set_screen_state(next_state: ScreenState) -> void:
	_screen_state = next_state
	var local_player := _battle.player() if _battle != null else null
	var can_act := next_state == ScreenState.PLAYER_INPUT and _battle != null and _battle.can_local_player_act()
	attack_button.disabled = not can_act or _target_enemy_id == 0
	skill_button.disabled = not can_act or local_player == null or not local_player.job_skills().any(func(skill): return bool(skill.get("can_use", false)))
	item_button.disabled = not can_act or local_player == null or not local_player.consumables.any(func(item): return bool(item.get("can_use", false)))
	var busy := next_state in [ScreenState.LOADING, ScreenState.SUBMITTING, ScreenState.PLAYING_RESULT]
	forfeit_button.disabled = busy or _battle == null or not _battle.is_in_progress() or (local_player != null and local_player.has_left)
	back_button.disabled = next_state in [ScreenState.SUBMITTING, ScreenState.PLAYING_RESULT]
	if next_state != ScreenState.PLAYER_INPUT and _choice_popup != null:
		_choice_popup.hide()

	var actor := _battle.current_actor() if _battle != null else null
	var waiting_for_player := next_state == ScreenState.WAITING and actor != null and actor != local_player
	skip_idle_button.visible = waiting_for_player and not _repository.use_mock
	if next_state == ScreenState.WAITING and not _repository.use_mock:
		if poll_timer.is_stopped():
			poll_timer.start()
	else:
		poll_timer.stop()

	match next_state:
		ScreenState.LOADING:
			connection_status.text = "LOADING"
			hint_label.text = ""
		ScreenState.SUBMITTING:
			connection_status.text = "SENDING ACTION"
		ScreenState.PLAYING_RESULT:
			connection_status.text = "RESOLVING TURN"
		ScreenState.BATTLE_ENDED:
			connection_status.text = "BATTLE COMPLETE"
			hint_label.text = "The battle is over."
		ScreenState.WAITING:
			connection_status.text = "WAITING"
			if local_player != null and not local_player.is_alive():
				hint_label.text = "You are down. Your party fights on."
			elif waiting_for_player:
				hint_label.text = "Waiting for %s to act..." % actor.display_name
			else:
				hint_label.text = "The monsters are acting..."
		_:
			connection_status.text = "MOCK SERVER" if _repository.use_mock else "LIVE SERVER"
			hint_label.text = "Your turn. Click an enemy to target it, then attack, use a skill or an item."


func _phase_text() -> String:
	match _battle.status:
		"victory":
			return "VICTORY"
		"defeat":
			return "DEFEAT"
	return "MONSTER PHASE" if _battle.turn_phase == "monster_phase" else "PLAYER PHASE"


func _setup_choice_popup() -> void:
	_choice_popup = PopupPanel.new()
	_choice_popup.name = "ChoicePopup"
	_choice_popup.unresizable = true
	add_child(_choice_popup)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 8)
	_choice_popup.add_child(margin)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 8)
	margin.add_child(root)
	_choice_title = Label.new()
	_choice_title.add_theme_color_override("font_color", Color("66c9f5"))
	_choice_title.add_theme_font_size_override("font_size", 14)
	root.add_child(_choice_title)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	root.add_child(scroll)
	_choice_list = VBoxContainer.new()
	_choice_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_choice_list.add_theme_constant_override("separation", 6)
	scroll.add_child(_choice_list)


## Opens a list of choices above `anchor`. Each entry: {"text", "tooltip", "disabled", "pick": Callable}.
func _open_choices(title: String, entries: Array, anchor: Control, empty_text: String) -> void:
	if _choice_popup.visible:
		_choice_popup.hide()
		return
	_choice_title.text = title
	for child in _choice_list.get_children():
		child.free()
	if entries.is_empty():
		var empty := Label.new()
		empty.text = empty_text
		empty.add_theme_color_override("font_color", Color("7f8d9d"))
		_choice_list.add_child(empty)
	for entry in entries:
		var button := Button.new()
		button.custom_minimum_size = Vector2(350, 58)
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.text = str(entry.text)
		button.tooltip_text = str(entry.get("tooltip", ""))
		button.disabled = bool(entry.get("disabled", false))
		button.add_theme_font_size_override("font_size", 13)
		var pick: Callable = entry.pick
		button.pressed.connect(func():
			_choice_popup.hide()
			pick.call()
		)
		_choice_list.add_child(button)
	var height := mini(380, 54 + maxi(1, entries.size()) * 64)
	var anchor_position := anchor.get_screen_position()
	var right_edge := int(get_viewport_rect().size.x) - 370 - 10
	_choice_popup.popup(Rect2i(
		Vector2i(mini(int(anchor_position.x), right_edge), maxi(10, int(anchor_position.y) - height - 8)),
		Vector2i(370, height)
	))


func _append_log(message: String, color: Color = LOG_COLOR) -> void:
	combat_log.push_color(color)
	combat_log.add_text("• %s\n" % message)
	combat_log.pop()
