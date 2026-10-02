class_name BattleRepository
extends RefCounted

## Battle API access. With use_mock the offline MockBattleServer answers instead.
## Action responses are normalized to {"ok", "status", "data": {"events", "combat"}}.

var use_mock: bool = true
var _mock := MockBattleServer.new()


func reset_mock() -> void:
	_mock.reset()


func load_battle(combat_id: String) -> Dictionary:
	if use_mock:
		return {"ok": true, "status": 200, "data": _mock.snapshot()}
	return await ApiClient.get_json("battles/%s/" % combat_id.uri_encode())


static func attack_payload(target: CombatantState) -> Dictionary:
	return {"action_type": "ATTACK", "target_id": target.id}


## SELF and area skills go without a target; the server resolves them.
static func skill_payload(skill: Dictionary, target: CombatantState) -> Dictionary:
	var payload := {"action_type": "SKILL", "character_skill_id": int(skill.get("character_skill_id", 0))}
	if target != null and str(skill.get("target_type", "ENEMY")) in ["ENEMY", "ALLY"]:
		payload["target_id"] = target.id
	return payload


static func item_payload(item: Dictionary, target: CombatantState) -> Dictionary:
	var payload := {"action_type": "ITEM", "inventory_item_id": int(item.get("inventory_item_id", 0))}
	if target != null:
		payload["target_id"] = target.id
	return payload


## Sends an action built from `battle`. expected_version makes the server refuse
## an action built from an outdated snapshot (409); client_action_id makes a
## retry after a network failure replay the first result instead of acting twice.
func submit_action(battle: BattleState, payload: Dictionary) -> Dictionary:
	var request := payload.duplicate()
	request["expected_version"] = battle.version
	request["client_action_id"] = new_action_id()
	if use_mock:
		return _mock.act(request)
	var path := "battles/%s/action/" % battle.id.uri_encode()
	var response: Dictionary = await ApiClient.post_json(path, request)
	if int(response.get("status", 0)) == 0:
		response = await ApiClient.post_json(path, request)
	return _normalize(response)


func forfeit(combat_id: String) -> Dictionary:
	if use_mock:
		return _mock.forfeit()
	return _normalize(await ApiClient.post_json("battles/%s/forfeit/" % combat_id.uri_encode()))


func skip_idle_turn(combat_id: String) -> Dictionary:
	if use_mock:
		return {"ok": false, "status": 400, "error": {"code": "BATTLE_ERROR", "message": "Offline battles have no other players."}}
	return _normalize(await ApiClient.post_json("battles/%s/skip-idle-turn/" % combat_id.uri_encode()))


## Starts a new battle in a normal dungeon; returns the new combat ID in data.
func enter_normal_dungeon(dungeon_id: int) -> Dictionary:
	if use_mock:
		_mock.reset()
		return {"ok": true, "status": 201, "data": {"combat_instance_id": _mock.snapshot().id}}
	return await ApiClient.post_json("world/normal-dungeons/%d/enter/" % dungeon_id)


## A random UUID v4.
static func new_action_id() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 0x0f) | 0x40
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	var hex := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [hex.substr(0, 8), hex.substr(8, 4), hex.substr(12, 4), hex.substr(16, 4), hex.substr(20, 12)]


## A dead player's request answers {"detail", "events"}; keep the detail as a log line.
static func _normalize(response: Dictionary) -> Dictionary:
	if not response.get("ok", false):
		if int(response.get("status", 0)) == 409:
			var conflict := response.duplicate(true)
			conflict["error"] = {"code": "VERSION_CONFLICT", "message": ApiClient.error_message(response, "The battle changed. Reloading.")}
			return conflict
		return response
	var payload: Dictionary = response.get("data", {})
	var events: Array = payload.get("events", []).duplicate()
	if payload.get("detail") is String:
		events.push_front({"event_type": "notice", "message": payload.detail})
	return {
		"ok": true,
		"status": response.get("status", 200),
		"data": {"events": events, "combat": payload.get("combat", {})},
	}
