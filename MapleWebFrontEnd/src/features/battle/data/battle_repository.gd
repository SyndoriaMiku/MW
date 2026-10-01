class_name BattleRepository
extends RefCounted

## Keep this true until the backend has a configured demo dungeon and a live
## combat instance. The presentation layer does not need to change when this is
## switched off.
var use_mock: bool = true
var _mock_battle: Dictionary = {}


func _init() -> void:
	reset_mock()


func reset_mock() -> void:
	_mock_battle = {
		"id": "demo-1v1",
		"status": "in_progress",
		"turn_phase": "player_phase",
		"turn_count": 1,
		"current_player_position": 1,
		"combatants": [
			{
				"id": 1,
				"entity_id": "demo-player",
				"name": "Adventurer",
				"is_player": true,
				"current_hp": 100,
				"current_mp": 20,
				"max_hp": 100,
				"max_mp": 20,
				"position": 1,
				"skill_cooldowns": {},
				"valid_actions": ["ATTACK", "SKILL"],
				"is_current_actor": true,
				"skills": [
					{
						"character_skill_id": 1, "skill_template_id": 1,
						"name": "Normal Attack", "level": 1,
						"target_type": "ENEMY", "effect_type": "DAMAGE",
						"is_basic_attack": true, "mp_cost": 0, "cooldown": 0,
						"cooldown_remaining": 0, "damage_multiplier": 1.0, "can_use": true,
					},
					{
						"character_skill_id": 2, "skill_template_id": 2,
						"name": "Power Strike", "level": 1,
						"target_type": "ENEMY", "effect_type": "DAMAGE",
						"is_basic_attack": false, "mp_cost": 5, "cooldown": 3,
						"cooldown_remaining": 0, "damage_multiplier": 1.5, "can_use": true,
					},
				],
				"active_effects": [],
			},
			{
				"id": 2,
				"entity_id": "1",
				"name": "Little Wolf",
				"is_player": false,
				"current_hp": 70,
				"current_mp": 2,
				"max_hp": 70,
				"max_mp": 2,
				"position": 2,
				"skill_cooldowns": {},
				"active_effects": [],
			},
		],
	}


func load_battle(combat_id: String) -> Dictionary:
	if use_mock:
		return {"ok": true, "data": _mock_battle.duplicate(true)}
	return await ApiClient.get_json("battles/%s/" % combat_id)


func submit_attack(combat_id: String, target: CombatantState) -> Dictionary:
	if use_mock:
		return _resolve_mock_attack(target.id)
	var response: Dictionary = await ApiClient.post_json(
		"battles/%s/action/" % combat_id,
		{"action_type": "ATTACK", "target_position": target.position}
	)
	return _normalize_action_response(response)


func submit_skill(combat_id: String, skill: Dictionary, target: CombatantState) -> Dictionary:
	if use_mock:
		return _resolve_mock_skill(skill, target.id if target != null else 0)
	var payload := {
		"action_type": "SKILL",
		"character_skill_id": int(skill.get("character_skill_id", 0)),
	}
	var target_type := str(skill.get("target_type", "ENEMY"))
	if target != null and target_type in ["ENEMY", "ALLY", "SELF"]:
		payload["target_id"] = target.id
	var response: Dictionary = await ApiClient.post_json(
		"battles/%s/action/" % combat_id,
		payload
	)
	return _normalize_action_response(response)


func _normalize_action_response(response: Dictionary) -> Dictionary:
	if not response.get("ok", false):
		return response

	var payload: Dictionary = response.get("data", {})
	var events: Array = payload.get("events", [])
	if events.is_empty() and payload.has("action_log"):
		var action_log: Dictionary = payload.get("action_log", {})
		if action_log.has("damage"):
			events.append({
				"type": "damage_applied",
				"actor_name": action_log.get("actor", "Player"),
				"target_name": action_log.get("target", "Enemy"),
				"amount": action_log.get("damage", 0),
			})
		elif action_log.has("message"):
			events.append({"type": "combat_message", "message": action_log.message})

	return {
		"ok": true,
		"status": response.get("status", 200),
		"data": {
			"events": events,
			"combat": payload.get("combat", payload),
		},
	}


func _resolve_mock_skill(skill: Dictionary, target_id: int) -> Dictionary:
	var player := _find_mock_combatant(1)
	var enemy := _find_mock_combatant(target_id)
	var cooldown_remaining := int(skill.get("cooldown_remaining", 0))
	var mp_cost := int(skill.get("mp_cost", 0))
	if player.is_empty() or enemy.is_empty() or cooldown_remaining > 0 or int(player.current_mp) < mp_cost:
		return {
			"ok": false,
			"error": {"code": "SKILL_UNAVAILABLE", "message": "This skill cannot be used right now."},
		}
	player.current_mp = int(player.current_mp) - mp_cost
	var skill_template_id := str(skill.get("skill_template_id", ""))
	player.skill_cooldowns[skill_template_id] = int(skill.get("cooldown", 0))
	var damage := maxi(1, int(22.0 * float(skill.get("damage_multiplier", 1.0))))
	enemy.current_hp = maxi(0, int(enemy.current_hp) - damage)
	var events: Array = [{
		"action": "SKILL",
		"actor": player.name,
		"target": enemy.name,
		"skill_name": skill.get("name", "Skill"),
		"damage": damage,
		"message": "%s used %s and dealt %d damage to %s." % [player.name, skill.get("name", "Skill"), damage, enemy.name],
	}]
	_finish_mock_turn(player, enemy, events)
	return {"ok": true, "data": {"events": events, "combat": _mock_battle.duplicate(true)}}


func _resolve_mock_attack(target_id: int) -> Dictionary:
	var events: Array = []
	var player := _find_mock_combatant(1)
	var enemy := _find_mock_combatant(target_id)
	if player.is_empty() or enemy.is_empty() or _mock_battle.status != "in_progress":
		return {
			"ok": false,
			"error": {"code": "INVALID_MOCK_ACTION", "message": "The action is no longer valid."},
		}

	var player_damage := 22
	enemy.current_hp = maxi(0, int(enemy.current_hp) - player_damage)
	events.append({
		"type": "damage_applied",
		"actor_name": player.name,
		"target_name": enemy.name,
		"amount": player_damage,
	})

	_finish_mock_turn(player, enemy, events)
	return {
		"ok": true,
		"data": {
			"events": events,
			"combat": _mock_battle.duplicate(true),
		},
	}


## Resolves victory, or the enemy's counter-attack and the possible defeat, after
## the player's action.
func _finish_mock_turn(player: Dictionary, enemy: Dictionary, events: Array) -> void:
	if int(enemy.current_hp) <= 0:
		_mock_battle.status = "victory"
		events.append({"type": "combatant_defeated", "target_name": enemy.name})
		events.append({"type": "battle_victory"})
		return

	var enemy_damage := 9
	player.current_hp = maxi(0, int(player.current_hp) - enemy_damage)
	events.append({
		"type": "damage_applied",
		"actor_name": enemy.name,
		"target_name": player.name,
		"amount": enemy_damage,
	})
	if int(player.current_hp) <= 0:
		_mock_battle.status = "defeat"
		events.append({"type": "combatant_defeated", "target_name": player.name})
		events.append({"type": "battle_defeat"})
		return

	_advance_mock_player_cooldowns()
	_mock_battle.turn_count = int(_mock_battle.turn_count) + 1
	events.append({"type": "turn_started", "turn": _mock_battle.turn_count})


func _find_mock_combatant(combatant_id: int) -> Dictionary:
	for combatant in _mock_battle.combatants:
		if int(combatant.id) == combatant_id:
			return combatant
	return {}


func _advance_mock_player_cooldowns() -> void:
	var player := _find_mock_combatant(1)
	if player.is_empty():
		return
	for skill_value in player.get("skills", []):
		if not skill_value is Dictionary:
			continue
		var skill: Dictionary = skill_value
		var template_id := str(skill.get("skill_template_id", ""))
		var remaining := maxi(0, int(player.skill_cooldowns.get(template_id, 0)) - 1)
		player.skill_cooldowns[template_id] = remaining
		skill["cooldown_remaining"] = remaining
		skill["can_use"] = remaining <= 0 and int(player.current_mp) >= int(skill.get("mp_cost", 0))
