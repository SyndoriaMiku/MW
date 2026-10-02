extends Node

## Battle domain, backend-shaped events, the offline mock and the battle screen.


func _ready() -> void:
	if not _check_events() or not _check_local_player() or not await _check_mock_server():
		return
	if not await _check_screen():
		return
	print("BATTLE_OK")
	get_tree().quit(0)


## Events shaped like MapleWebBackEnd/apps/battles/services.py.
func _check_events() -> bool:
	var action := {
		"event_type": "action", "actor_type": "character", "actor": "Hero", "success": true,
		"message": "Hero used Whirlwind: dealt 12 damage to Wolf; dealt 5 damage to Slime.",
		"targets": [
			{"target_id": 4, "damage": 12, "shield_absorbed": 0, "heal": 0},
			{"target_id": 5, "damage": 0, "shield_absorbed": 7, "heal": 0},
		],
		"battle_result": {"status": "victory", "rewards": {"Hero": {"exp_gained": 30, "lumis_gained": 5, "items_dropped": [{"name": "Iron Essence", "qty": 2}], "level_up": true}}},
	}
	var lines := BattleEvents.log_lines(action)
	if lines.size() != 2 or lines[1].text != "Victory!":
		return _fail("ACTION_LOG_LINES_FAILED %s" % [lines])
	var hits := BattleEvents.hits(action)
	if hits.size() != 2 or hits[0].kind != "damage" or hits[0].amount != 12 or hits[1].kind != "blocked":
		return _fail("ACTION_HITS_FAILED %s" % [hits])
	if not BattleEvents.hits({"event_type": "action", "success": false, "targets": [{"target_id": 1, "damage": 9}]}).is_empty():
		return _fail("BLOCKED_ACTION_HAS_HITS")

	var tick := {"event_type": "effect_tick", "effect": "Ignite", "target": "Wolf", "target_id": 4, "hp_change": -6, "mp_change": 0, "is_dead": true, "expired": true}
	var tick_text := " | ".join(BattleEvents.log_lines(tick).map(func(line): return line.text))
	if not tick_text.contains("takes 6 damage from Ignite") or not tick_text.contains("was defeated") or not tick_text.contains("wore off"):
		return _fail("EFFECT_TICK_LINES_FAILED %s" % tick_text)
	if BattleEvents.hits(tick) != [{"target_id": 4, "amount": 6, "kind": "damage"}]:
		return _fail("EFFECT_TICK_HITS_FAILED")

	var result := BattleEvents.battle_result([{"event_type": "action"}, action])
	if result.get("status") != "victory" or BattleEvents.rewards_for(result, "Hero").get("exp_gained") != 30:
		return _fail("BATTLE_RESULT_FAILED")
	var screen_script: GDScript = load("res://src/features/battle/presentation/battle_screen.gd")
	var summary: String = screen_script.result_summary(true, result, "Hero", false, true)
	if not summary.contains("EXP  +30") or not summary.contains("LEVEL UP!") or not summary.contains("Iron Essence ×2"):
		return _fail("RESULT_SUMMARY_FAILED %s" % summary)
	if not screen_script.result_summary(false, {}, "Hero", false, true).contains("No stamina was spent"):
		return _fail("DEFEAT_SUMMARY_FAILED")
	var skill_text: String = screen_script.skill_entry_text({"name": "Power Strike", "level": 1, "cooldown_remaining": 2, "mp_cost": 5, "target_type": "E_AREA"})
	if not skill_text.contains("CD 2 TURNS") or not skill_text.contains("All enemies"):
		return _fail("SKILL_ENTRY_TEXT_FAILED %s" % skill_text)
	return true


## In a party battle the signed-in character is found by entity ID, not by order.
func _check_local_player() -> bool:
	var battle := BattleState.from_dict({
		"id": "abc", "version": 3, "status": "in_progress", "turn_phase": "player_phase", "current_player_position": 2,
		"combatants": [
			{"id": 1, "entity_id": "aaa", "is_player": true, "name": "Ally", "current_hp": 10, "max_hp": 10, "position": 1},
			{"id": 2, "entity_id": "bbb", "is_player": true, "name": "Me", "current_hp": 10, "max_hp": 10, "position": 2},
			{"id": 3, "entity_id": "7", "is_player": false, "name": "Wolf", "current_hp": 0, "max_hp": 10, "position": 3},
			{"id": 4, "entity_id": "8", "is_player": false, "name": "Slime", "current_hp": 5, "max_hp": 10, "position": 4},
		],
	}, "bbb")
	if battle.player().display_name != "Me" or not battle.can_local_player_act() or battle.version != 3:
		return _fail("LOCAL_PLAYER_FAILED")
	if battle.first_enemy().display_name != "Slime" or battle.enemies().size() != 2:
		return _fail("ENEMY_LOOKUP_FAILED")
	battle.current_player_position = 1
	if battle.can_local_player_act() or not battle.is_waiting_for_others() or battle.current_actor().display_name != "Ally":
		return _fail("WAITING_FOR_ALLY_FAILED")
	return true


func _check_mock_server() -> bool:
	var repository := BattleRepository.new()
	var battle := BattleState.from_dict((await repository.load_battle("")).data)
	var wolf := battle.combatant_by_id(2)
	var response: Dictionary = await repository.submit_action(battle, BattleRepository.attack_payload(wolf))
	var after := BattleState.from_dict(response.data.combat)
	if after.version != 1 or after.combatant_by_id(2).current_hp != 70 - MockBattleServer.BASIC_DAMAGE or after.turn_count != 2:
		return _fail("MOCK_ATTACK_FAILED %s" % response)
	var stale: Dictionary = await repository.submit_action(battle, BattleRepository.attack_payload(wolf))
	if stale.get("ok", true) or stale.error.code != "VERSION_CONFLICT":
		return _fail("MOCK_VERSION_CONFLICT_FAILED")

	var whirlwind: Dictionary = after.player().skills[2]
	response = await repository.submit_action(after, BattleRepository.skill_payload(whirlwind, null))
	var area_targets: Array = response.data.events[0].targets
	if area_targets.size() != 2:
		return _fail("MOCK_AREA_SKILL_FAILED")
	after = BattleState.from_dict(response.data.combat)
	var potion: Dictionary = after.player().consumables[0]
	response = await repository.submit_action(after, BattleRepository.item_payload(potion, after.player()))
	if int(response.data.events[0].heal) <= 0 or BattleState.from_dict(response.data.combat).player().consumables[0].quantity != 2:
		return _fail("MOCK_ITEM_FAILED %s" % response.data.events[0])

	repository.reset_mock()
	response = await repository.forfeit("")
	if BattleEvents.battle_result(response.data.events).get("status") != "defeat":
		return _fail("MOCK_FORFEIT_FAILED")
	if not BattleRepository.new_action_id().match("????????-????-4???-????-????????????"):
		return _fail("ACTION_ID_FORMAT_FAILED")
	return true


func _check_screen() -> bool:
	SessionStore.active_battle_id = ""
	var screen: Control = load("res://src/features/battle/presentation/battle_screen.tscn").instantiate()
	screen.event_delay = 0.01
	add_child(screen)
	if not await _wait_for(func(): return screen._battle != null and screen._screen_state == screen.ScreenState.PLAYER_INPUT):
		return _fail("SCREEN_LOAD_FAILED")
	if screen.party_list.get_child_count() != 1 or screen.enemy_grid.get_child_count() != 2:
		return _fail("SCREEN_CARDS_FAILED")
	screen._on_card_pressed(3)
	if not screen.target_label.text.contains("Gray Slime"):
		return _fail("SCREEN_TARGET_FAILED %s" % screen.target_label.text)
	await screen._on_attack_pressed()
	if screen._battle.combatant_by_id(3).current_hp != 45 - MockBattleServer.BASIC_DAMAGE or not screen.combat_log.get_parsed_text().contains("Gray Slime"):
		return _fail("SCREEN_ATTACK_FAILED")

	# Fight on until the battle ends; the mock enemies cannot win this fast.
	for turn in 12:
		if not screen._battle.is_in_progress():
			break
		var whirlwind: Dictionary = screen._battle.player().skills[2]
		if bool(whirlwind.get("can_use", false)):
			await screen._use_skill(whirlwind)
		else:
			await screen._on_attack_pressed()
	if screen._battle.status != "victory" or not screen.result_overlay.visible or not screen.rewards_label.text.contains("EXP  +20"):
		return _fail("SCREEN_VICTORY_FAILED status=%s rewards=%s" % [screen._battle.status, screen.rewards_label.text])
	await screen._on_again_pressed()
	if screen.result_overlay.visible or not screen._battle.is_in_progress():
		return _fail("SCREEN_PLAY_AGAIN_FAILED")
	screen.queue_free()
	return true


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
