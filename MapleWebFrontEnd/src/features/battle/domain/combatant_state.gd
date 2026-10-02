class_name CombatantState
extends RefCounted

var id: int
var entity_id: String
var entity_type: String
var display_name: String
var visual_key: String
var is_player: bool
var has_left: bool
var current_hp: int
var current_mp: int
var max_hp: int
var max_mp: int
var position: int
var skill_cooldowns: Dictionary
var skills: Array
var consumables: Array
var valid_actions: Array
var is_current_actor: bool
var active_effects: Array


static func from_dict(data: Dictionary) -> CombatantState:
	var combatant := CombatantState.new()
	combatant.id = int(data.get("id", 0))
	combatant.entity_id = ApiClient.id_string(data.get("entity_id"))
	combatant.is_player = bool(data.get("is_player", false))
	combatant.entity_type = str(data.get("entity_type", "character" if combatant.is_player else "enemy"))
	combatant.display_name = str(data.get("name", "Unknown"))
	combatant.visual_key = str(data.get("visual_key", ""))
	combatant.has_left = bool(data.get("has_left", false))
	combatant.current_hp = int(data.get("current_hp", 0))
	combatant.current_mp = int(data.get("current_mp", 0))
	combatant.max_hp = maxi(1, int(data.get("max_hp", 1)))
	combatant.max_mp = maxi(1, int(data.get("max_mp", 1)))
	combatant.position = int(data.get("position", 0))
	combatant.skill_cooldowns = _dictionary(data.get("skill_cooldowns"))
	combatant.skills = _array(data.get("skills"))
	combatant.consumables = _array(data.get("consumables"))
	combatant.valid_actions = _array(data.get("valid_actions"))
	combatant.is_current_actor = bool(data.get("is_current_actor", false))
	combatant.active_effects = _array(data.get("active_effects"))
	return combatant


func is_alive() -> bool:
	return current_hp > 0


## Job skills the player can pick from the skill menu (the basic attack has its own button).
func job_skills() -> Array:
	return skills.filter(func(skill):
		return skill is Dictionary and not bool(skill.get("is_basic_attack", false)) and not bool(skill.get("is_passive", false))
	)


func effect_names() -> PackedStringArray:
	var names := PackedStringArray()
	for effect in active_effects:
		if effect is Dictionary:
			names.append("%s (%d)" % [str(effect.get("effect_name", "Effect")), int(effect.get("remaining_turns", 0))])
	return names


static func _dictionary(value: Variant) -> Dictionary:
	return value.duplicate(true) if value is Dictionary else {}


static func _array(value: Variant) -> Array:
	return value.duplicate(true) if value is Array else []
