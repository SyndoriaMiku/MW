class_name BattleEvents
extends RefCounted

## Reads the battle events produced by MapleWebBackEnd/apps/battles/services.py
## ("action", "effect_tick", "turn_skipped", "forfeit", plus an optional
## "battle_result") and turns them into log lines, floating numbers and the
## battle outcome.

const COLOR_PLAYER := M3.PRIMARY
const COLOR_ENEMY := M3.ERROR
const COLOR_INFO := M3.ON_SURFACE_VARIANT
const COLOR_WARNING := M3.GOLD
const COLOR_VICTORY := M3.SUCCESS
const COLOR_DEFEAT := M3.ERROR


## [{"text": String, "color": Color}] for the combat log.
static func log_lines(event: Dictionary) -> Array:
	var lines: Array = []
	var message := str(event.get("message", ""))
	match str(event.get("event_type", "")):
		"action":
			if not bool(event.get("success", true)):
				lines.append(_line(message, COLOR_WARNING))
			elif not message.is_empty():
				lines.append(_line(message, COLOR_PLAYER if event.get("actor_type") == "character" else COLOR_ENEMY))
		"effect_tick":
			lines.append_array(_effect_tick_lines(event))
		"forfeit", "turn_skipped":
			lines.append(_line(message, COLOR_WARNING))
		_:
			if not message.is_empty():
				lines.append(_line(message, COLOR_INFO))

	var result: Variant = event.get("battle_result")
	if result is Dictionary:
		var status := str(result.get("status", ""))
		if status == "victory":
			lines.append(_line("Victory!", COLOR_VICTORY))
		elif status == "defeat":
			lines.append(_line("Defeat.", COLOR_DEFEAT))
	return lines


## Numbers to float over combatants: [{"target_id": int, "amount": int, "kind": String}]
## where kind is "damage", "heal", "mp" or "blocked".
static func hits(event: Dictionary) -> Array:
	var result: Array = []
	match str(event.get("event_type", "")):
		"action":
			if not bool(event.get("success", true)):
				return result
			for target_value in event.get("targets", []):
				if not target_value is Dictionary:
					continue
				var target: Dictionary = target_value
				var target_id := int(target.get("target_id", 0))
				var damage := int(target.get("damage", 0))
				var shield := int(target.get("shield_absorbed", 0))
				if damage > 0:
					result.append(_hit(target_id, damage, "damage"))
				elif shield > 0:
					result.append(_hit(target_id, shield, "blocked"))
				if int(target.get("heal", 0)) > 0:
					result.append(_hit(target_id, int(target.heal), "heal"))
				if int(target.get("mp_restored", 0)) > 0:
					result.append(_hit(target_id, int(target.mp_restored), "mp"))
		"effect_tick":
			var target_id := int(event.get("target_id", 0))
			var hp_change := int(event.get("hp_change", 0))
			if hp_change < 0:
				result.append(_hit(target_id, -hp_change, "damage"))
			elif hp_change > 0:
				result.append(_hit(target_id, hp_change, "heal"))
			if int(event.get("mp_change", 0)) > 0:
				result.append(_hit(target_id, int(event.mp_change), "mp"))
	return result


## The last battle_result in the events, or {} when the battle goes on.
## Shape: {"status": "victory" | "defeat", "rewards": {character_name: {...}} | null}
static func battle_result(events: Array) -> Dictionary:
	var found := {}
	for event in events:
		if event is Dictionary and event.get("battle_result") is Dictionary:
			found = event.battle_result
	return found


## The rewards one character got from a victory:
## {"exp_gained", "lumis_gained", "items_dropped": [{"name", "qty"}], "level_up"}.
static func rewards_for(result: Dictionary, character_name: String) -> Dictionary:
	var rewards: Variant = result.get("rewards")
	if not rewards is Dictionary:
		return {}
	var own: Variant = rewards.get(character_name)
	return own if own is Dictionary else {}


static func _effect_tick_lines(event: Dictionary) -> Array:
	var lines: Array = []
	var target := str(event.get("target", "Someone"))
	var effect := str(event.get("effect", "an effect"))
	var color := COLOR_PLAYER if event.get("target_type") == "character" else COLOR_ENEMY
	var hp_change := int(event.get("hp_change", 0))
	var mp_change := int(event.get("mp_change", 0))
	if hp_change < 0:
		lines.append(_line("%s takes %d damage from %s." % [target, -hp_change, effect], color))
	elif hp_change > 0:
		lines.append(_line("%s recovers %d HP from %s." % [target, hp_change, effect], color))
	if mp_change != 0:
		lines.append(_line("%s %s %d MP from %s." % [target, "recovers" if mp_change > 0 else "loses", absi(mp_change), effect], color))
	if bool(event.get("is_dead", false)):
		lines.append(_line("%s was defeated." % target, color))
	if bool(event.get("expired", false)):
		lines.append(_line("%s wore off %s." % [effect, target], COLOR_INFO))
	return lines


static func _line(text: String, color: Color) -> Dictionary:
	return {"text": text, "color": color}


static func _hit(target_id: int, amount: int, kind: String) -> Dictionary:
	return {"target_id": target_id, "amount": amount, "kind": kind}
