class_name CombatantState
extends RefCounted

var id: int
var entity_id: String
var display_name: String
var is_player: bool
var current_hp: int
var current_mp: int
var max_hp: int
var max_mp: int
var position: int
var skill_cooldowns: Dictionary
var skills: Array
var valid_actions: Array
var is_current_actor: bool
var active_effects: Array


static func from_dict(data: Dictionary) -> CombatantState:
	var combatant := CombatantState.new()
	combatant.id = int(data.get("id", 0))
	combatant.entity_id = str(data.get("entity_id", ""))
	combatant.display_name = str(data.get("name", "Unknown"))
	combatant.is_player = bool(data.get("is_player", false))
	combatant.current_hp = int(data.get("current_hp", 0))
	combatant.current_mp = int(data.get("current_mp", 0))
	combatant.max_hp = maxi(1, int(data.get("max_hp", 1)))
	combatant.max_mp = maxi(1, int(data.get("max_mp", 1)))
	combatant.position = int(data.get("position", 0))
	combatant.skill_cooldowns = data.get("skill_cooldowns", {}).duplicate(true)
	combatant.skills = data.get("skills", []).duplicate(true)
	combatant.valid_actions = data.get("valid_actions", []).duplicate(true)
	combatant.is_current_actor = bool(data.get("is_current_actor", false))
	combatant.active_effects = data.get("active_effects", []).duplicate(true)
	return combatant


func is_alive() -> bool:
	return current_hp > 0
