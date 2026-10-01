class_name BattleState
extends RefCounted

var id: String
var status: String
var turn_phase: String
var turn_count: int
var current_player_position: int
var combatants: Array[CombatantState] = []


static func from_dict(data: Dictionary) -> BattleState:
	var battle := BattleState.new()
	battle.id = ApiClient.id_string(data.get("id"))
	battle.status = str(data.get("status", "in_progress"))
	battle.turn_phase = str(data.get("turn_phase", "player_phase"))
	battle.turn_count = int(data.get("turn_count", 1))
	battle.current_player_position = int(data.get("current_player_position", 1))
	for item in data.get("combatants", []):
		if item is Dictionary:
			battle.combatants.append(CombatantState.from_dict(item))
	return battle


func player() -> CombatantState:
	for combatant in combatants:
		if combatant.is_player:
			return combatant
	return null


func first_enemy() -> CombatantState:
	for combatant in combatants:
		if not combatant.is_player:
			return combatant
	return null


func can_local_player_act() -> bool:
	var local_player := player()
	return (
		status == "in_progress"
		and turn_phase == "player_phase"
		and local_player != null
		and local_player.position == current_player_position
		and local_player.is_alive()
	)

