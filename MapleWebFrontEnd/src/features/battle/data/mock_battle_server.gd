class_name MockBattleServer
extends RefCounted

## Offline stand-in for the battle API. Returns the same shapes as the backend
## (CombatInstanceSerializer snapshots and services.py events) so every battle
## screen feature can run without a server.

const PLAYER_ID := 1
const BASIC_DAMAGE := 22
const REWARDS := {"exp_gained": 20, "lumis_gained": 15, "items_dropped": [{"name": "Copper Essence", "qty": 1}], "level_up": false}

var _state: Dictionary = {}


func _init() -> void:
	reset()


func reset() -> void:
	_state = {
		"id": "demo-1v2",
		"version": 0,
		"status": "in_progress",
		"turn_phase": "player_phase",
		"turn_count": 1,
		"turn_started_at": null,
		"current_player_position": 1,
		"encounter": {"type": "custom", "id": null, "name": "Training Ground (offline)"},
		"combatants": [
			_player(),
			_enemy(2, "Little Wolf", 70, 9, 2),
			_enemy(3, "Gray Slime", 45, 6, 3),
		],
	}


func snapshot() -> Dictionary:
	for combatant in _state.combatants:
		_refresh_player_view(combatant)
	return _state.duplicate(true)


## Mirrors POST battles/<id>/action/.
func act(payload: Dictionary) -> Dictionary:
	var player := _find(PLAYER_ID)
	if _state.status != "in_progress":
		return _error(400, "This battle has already ended.")
	if payload.has("expected_version") and int(payload.expected_version) != int(_state.version):
		return _error(409, "The battle has changed since this action was built. Reload and retry.")

	var log := _action_log(player, str(payload.get("action_type", "ATTACK")))
	match log.action:
		"ATTACK":
			var target := _find(int(payload.get("target_id", 0)))
			if target.is_empty() or target.is_player or int(target.current_hp) <= 0:
				return _blocked(log, "Basic attacks require a living enemy target.")
			log.skill_name = "Normal Attack"
			_strike(log, [target], BASIC_DAMAGE)
		"SKILL":
			var skill := _find_skill(int(payload.get("character_skill_id", 0)))
			var template_id := str(skill.get("skill_template_id", ""))
			if skill.is_empty() or int(player.skill_cooldowns.get(template_id, 0)) > 0 or int(player.current_mp) < int(skill.mp_cost):
				return _blocked(log, "This skill cannot be used right now.")
			var targets: Array = _living_enemies()
			if skill.target_type == "ENEMY":
				var target := _find(int(payload.get("target_id", 0)))
				if target.is_empty() or target.is_player or int(target.current_hp) <= 0:
					return _blocked(log, "%s needs a living enemy target." % skill.name)
				targets = [target]
			player.current_mp = int(player.current_mp) - int(skill.mp_cost)
			player.skill_cooldowns[template_id] = int(skill.cooldown)
			log.skill_name = skill.name
			_strike(log, targets, int(BASIC_DAMAGE * float(skill.damage_multiplier)))
		"ITEM":
			var item := _find_consumable(int(payload.get("inventory_item_id", 0)))
			var cooldown_key := "item:%d" % int(item.get("item_template_id", 0))
			if item.is_empty() or int(item.quantity) <= 0 or int(player.skill_cooldowns.get(cooldown_key, 0)) > 0:
				return _blocked(log, "This item cannot be used right now.")
			var healed := mini(int(item.hp_restore), int(player.max_hp) - int(player.current_hp))
			player.current_hp = int(player.current_hp) + healed
			item.quantity = int(item.quantity) - 1
			player.skill_cooldowns[cooldown_key] = int(item.cooldown)
			log.item_name = item.name
			log.heal = healed
			log.targets = [{"target_id": PLAYER_ID, "target_type": "character", "target": player.name, "damage": 0, "shield_absorbed": 0, "heal": healed, "is_dead": false}]
			log.message = "%s used %s: restored %d HP to %s." % [player.name, item.name, healed, player.name]
		_:
			return _error(400, "Unknown action.")

	var events: Array = [log]
	_check_battle_end(log)
	if _state.status == "in_progress":
		events.append_array(_monster_phase())
	_state.version = int(_state.version) + 1
	return {"ok": true, "status": 200, "data": {"action_log": log, "events": events, "combat": snapshot()}}


## Mirrors POST battles/<id>/forfeit/.
func forfeit() -> Dictionary:
	if _state.status != "in_progress":
		return _error(400, "This battle has already ended.")
	var player := _find(PLAYER_ID)
	player.current_hp = 0
	player.has_left = true
	_state.status = "defeat"
	_state.version = int(_state.version) + 1
	var event := {
		"event_type": "forfeit", "actor_id": PLAYER_ID, "actor_type": "character", "actor": player.name,
		"message": "%s left the battle." % player.name,
		"battle_result": {"status": "defeat", "rewards": null},
	}
	return {"ok": true, "status": 200, "data": {"events": [event], "combat": snapshot()}}


func _monster_phase() -> Array:
	var events: Array = []
	var player := _find(PLAYER_ID)
	for enemy in _living_enemies():
		var log := _action_log(enemy, "ATTACK")
		_strike(log, [player], int(enemy.attack))
		events.append(log)
		_check_battle_end(log)
		if _state.status != "in_progress":
			return events
	_state.turn_count = int(_state.turn_count) + 1
	for key in player.skill_cooldowns.keys():
		player.skill_cooldowns[key] = maxi(0, int(player.skill_cooldowns[key]) - 1)
	return events


func _strike(log: Dictionary, targets: Array, damage: int) -> void:
	var parts := PackedStringArray()
	for target in targets:
		var dealt := mini(damage, int(target.current_hp))
		target.current_hp = int(target.current_hp) - dealt
		var is_dead := int(target.current_hp) <= 0
		log.targets.append({
			"target_id": target.id, "target_type": "character" if target.is_player else "enemy",
			"target": target.name, "damage": dealt, "shield_absorbed": 0, "heal": 0, "is_dead": is_dead,
		})
		log.damage = int(log.damage) + dealt
		log.is_dead = log.is_dead or is_dead
		parts.append("dealt %d damage to %s%s" % [dealt, target.name, "; %s was defeated" % target.name if is_dead else ""])
	var first: Dictionary = targets[0]
	log.target_id = first.id
	log.target = first.name
	log.message = "%s used %s: %s." % [log.actor, log.get("skill_name", "Attack"), "; ".join(parts)]


func _check_battle_end(log: Dictionary) -> void:
	if int(_find(PLAYER_ID).current_hp) <= 0:
		_state.status = "defeat"
		log.battle_result = {"status": "defeat", "rewards": null}
	elif _living_enemies().is_empty():
		_state.status = "victory"
		log.battle_result = {"status": "victory", "rewards": {_find(PLAYER_ID).name: REWARDS.duplicate(true)}}


func _action_log(actor: Dictionary, action: String) -> Dictionary:
	return {
		"event_type": "action", "actor_id": actor.id, "actor_type": "character" if actor.is_player else "enemy",
		"actor": actor.name, "action": action, "target_id": null, "target": null,
		"damage": 0, "heal": 0, "targets": [], "is_dead": false, "message": "", "success": true,
	}


func _blocked(log: Dictionary, message: String) -> Dictionary:
	log.success = false
	log.message = message
	return {"ok": true, "status": 200, "data": {"action_log": log, "events": [log], "combat": snapshot()}}


func _error(status: int, message: String) -> Dictionary:
	var code := "VERSION_CONFLICT" if status == 409 else "BATTLE_ERROR"
	return {"ok": false, "status": status, "error": {"code": code, "message": message}}


func _refresh_player_view(combatant: Dictionary) -> void:
	if not combatant.is_player:
		return
	var acting: bool = _state.status == "in_progress" and _state.turn_phase == "player_phase" and int(combatant.current_hp) > 0
	combatant.is_current_actor = acting
	for skill in combatant.skills:
		var remaining := int(combatant.skill_cooldowns.get(str(skill.skill_template_id), 0))
		skill.cooldown_remaining = remaining
		skill.can_use = acting and remaining <= 0 and int(combatant.current_mp) >= int(skill.mp_cost)
	for item in combatant.consumables:
		var remaining := int(combatant.skill_cooldowns.get("item:%d" % int(item.item_template_id), 0))
		item.cooldown_remaining = remaining
		item.can_use = acting and remaining <= 0 and int(item.quantity) > 0
	var actions: Array = []
	if acting:
		actions.append("ATTACK")
		if combatant.skills.any(func(skill): return skill.can_use and not skill.is_basic_attack):
			actions.append("SKILL")
		if combatant.consumables.any(func(item): return item.can_use):
			actions.append("ITEM")
	combatant.valid_actions = actions


func _find(combatant_id: int) -> Dictionary:
	for combatant in _state.combatants:
		if int(combatant.id) == combatant_id:
			return combatant
	return {}


func _find_skill(character_skill_id: int) -> Dictionary:
	for skill in _find(PLAYER_ID).skills:
		if int(skill.character_skill_id) == character_skill_id and not skill.is_basic_attack:
			return skill
	return {}


func _find_consumable(inventory_item_id: int) -> Dictionary:
	for item in _find(PLAYER_ID).consumables:
		if int(item.inventory_item_id) == inventory_item_id:
			return item
	return {}


func _living_enemies() -> Array:
	return _state.combatants.filter(func(combatant): return not combatant.is_player and int(combatant.current_hp) > 0)


static func _player() -> Dictionary:
	return {
		"id": PLAYER_ID, "entity_id": "demo-player", "entity_type": "character", "name": "Adventurer",
		"visual_key": "character:demo", "is_player": true, "has_left": false,
		"current_hp": 100, "current_mp": 30, "max_hp": 100, "max_mp": 30, "position": 1,
		"skill_cooldowns": {}, "active_effects": [], "is_current_actor": true, "valid_actions": [],
		"skills": [
			_skill(1, 1, "Normal Attack", "ENEMY", true, 0, 0, 1.0),
			_skill(2, 2, "Power Strike", "ENEMY", false, 5, 3, 1.5),
			_skill(3, 3, "Whirlwind", "E_AREA", false, 8, 4, 0.8),
		],
		"consumables": [{
			"inventory_item_id": 50, "item_template_id": 90, "name": "Red Potion", "icon_key": null,
			"quantity": 3, "target_type": "SELF", "hp_restore": 35, "hp_restore_percent": 0.0,
			"mp_restore": 0, "mp_restore_percent": 0.0, "effect": null, "cooldown": 2,
			"cooldown_remaining": 0, "can_use": true,
		}],
	}


static func _skill(owned_id: int, template_id: int, name: String, target_type: String, is_basic: bool, mp_cost: int, cooldown: int, multiplier: float) -> Dictionary:
	return {
		"character_skill_id": owned_id, "skill_template_id": template_id, "name": name, "level": 1,
		"target_type": target_type, "effect_type": "DAMAGE", "is_basic_attack": is_basic, "is_passive": false,
		"mp_cost": mp_cost, "cooldown": cooldown, "cooldown_remaining": 0, "damage_multiplier": multiplier, "can_use": true,
	}


static func _enemy(combatant_id: int, name: String, hp: int, attack: int, position: int) -> Dictionary:
	return {
		"id": combatant_id, "entity_id": str(combatant_id), "entity_type": "enemy", "name": name,
		"visual_key": "enemy:%d" % combatant_id, "is_player": false, "has_left": false,
		"current_hp": hp, "current_mp": 0, "max_hp": hp, "max_mp": 1, "position": position,
		"skill_cooldowns": {}, "active_effects": [], "skills": [], "consumables": [],
		"is_current_actor": false, "valid_actions": [], "attack": attack,
	}
