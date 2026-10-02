class_name BattleState
extends RefCounted

## Snapshot of a CombatInstance as serialized by the backend.

const IN_PROGRESS := "in_progress"
const PLAYER_PHASE := "player_phase"

var id: String
var version: int
var status: String
var turn_phase: String
var turn_count: int
var turn_started_at: String
var current_player_position: int
## {"type": "normal_dungeon" | "boss_dungeon" | "custom", "id", "name"}
var encounter: Dictionary
var combatants: Array[CombatantState] = []
## Entity ID of the signed-in character; empty in offline mode.
var local_entity_id: String


static func from_dict(data: Dictionary, local_entity_id: String = "") -> BattleState:
	var battle := BattleState.new()
	battle.id = ApiClient.id_string(data.get("id"))
	battle.version = int(data.get("version", 0))
	battle.status = str(data.get("status", IN_PROGRESS))
	battle.turn_phase = str(data.get("turn_phase", PLAYER_PHASE))
	battle.turn_count = int(data.get("turn_count", 1))
	battle.turn_started_at = str(data.get("turn_started_at", ""))
	battle.current_player_position = int(data.get("current_player_position", 1))
	battle.encounter = data.get("encounter") if data.get("encounter") is Dictionary else {}
	battle.local_entity_id = local_entity_id
	for item in data.get("combatants", []):
		if item is Dictionary:
			battle.combatants.append(CombatantState.from_dict(item))
	return battle


func is_in_progress() -> bool:
	return status == IN_PROGRESS


## The signed-in player's combatant. Falls back to the first player when the
## character is unknown (offline mock) so a solo battle still works.
func player() -> CombatantState:
	var first_player: CombatantState = null
	for combatant in combatants:
		if not combatant.is_player:
			continue
		if not local_entity_id.is_empty() and combatant.entity_id == local_entity_id:
			return combatant
		if first_player == null:
			first_player = combatant
	return first_player


func players() -> Array[CombatantState]:
	var result: Array[CombatantState] = []
	for combatant in combatants:
		if combatant.is_player:
			result.append(combatant)
	return result


func enemies() -> Array[CombatantState]:
	var result: Array[CombatantState] = []
	for combatant in combatants:
		if not combatant.is_player:
			result.append(combatant)
	return result


func first_enemy() -> CombatantState:
	for enemy in enemies():
		if enemy.is_alive():
			return enemy
	var all_enemies := enemies()
	return all_enemies[0] if not all_enemies.is_empty() else null


func combatant_by_id(combatant_id: int) -> CombatantState:
	for combatant in combatants:
		if combatant.id == combatant_id:
			return combatant
	return null


## The player whose turn it is, or null outside the player phase.
func current_actor() -> CombatantState:
	if not is_in_progress() or turn_phase != PLAYER_PHASE:
		return null
	for combatant in combatants:
		if combatant.is_player and combatant.position == current_player_position:
			return combatant
	return null


func can_local_player_act() -> bool:
	var local_player := player()
	return (
		is_in_progress()
		and turn_phase == PLAYER_PHASE
		and local_player != null
		and local_player.position == current_player_position
		and local_player.is_alive()
		and not local_player.has_left
	)


## In a party battle another player may be acting; the client then polls.
func is_waiting_for_others() -> bool:
	var local_player := player()
	return is_in_progress() and not can_local_player_act() and local_player != null and not local_player.has_left
