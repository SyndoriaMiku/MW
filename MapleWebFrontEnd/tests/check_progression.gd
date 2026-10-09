extends Node

## Skills, quests and the world map: their rules, and the pages against a fake
## server (upgrading a skill, claiming a quest, starting a boss without a
## party creates one first).

const PORT := 18775

var _server := FakeHttpServer.new()
var _posts: Array = []
var _skill_level := 2
var _quest_status := "completed"


func _ready() -> void:
	if not _check_skill_rules() or not _check_quest_rules() or not _check_world_rules():
		return
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		_fail("FAKE_SERVER_LISTEN_FAILED")
		return
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.base_url = _server.base_url(PORT)
	SessionStore.begin_session("hero", "token", "")
	if not await _check_skills_page() or not await _check_quests_page() or not await _check_adventure_page():
		return
	print("PROGRESSION_OK posts=%s" % [_posts])
	get_tree().quit(0)


func _skill(level: int, materials: Array, required_level: int = 5) -> Dictionary:
	return {
		"id": 11, "character_skill_id": 11, "skill_name": "Arrow Rain", "level": level, "damage_multiplier": 1.5,
		"effect_type": "DAMAGE", "target_type": "E_AREA", "mp_cost": 10, "cooldown": 2,
		"next_upgrade": {"skill_level": level + 1, "required_char_level": required_level, "damage_multiplier": 1.75,
			"requires_materials": not materials.is_empty(), "required_materials": materials},
	}


func _check_skill_rules() -> bool:
	var owned := SkillRules.owned_counts([{"template": {"id": 7}, "quantity": 2}, {"template": {"id": 7.0}, "quantity": 3}])
	if owned.get("7") != 5:
		return _fail("OWNED_COUNTS_FAILED %s" % [owned])
	var materials := [{"item_template_id": 7, "quantity": 4}]
	var cases := [
		[_skill(1, []), 9, "auto"], [_skill(1, materials, 10), 9, "level"],
		[_skill(1, [{"item_template_id": 7, "quantity": 9}]), 9, "materials"], [_skill(1, materials), 9, "ready"],
	]
	for case in cases:
		var state := SkillRules.upgrade_state(case[0], case[1], owned)
		if state.kind != case[2]:
			return _fail("UPGRADE_STATE_FAILED expected %s got %s" % [case[2], state.kind])
	var maxed := _skill(10, [])
	maxed["next_upgrade"] = null
	if SkillRules.upgrade_state(maxed, 99, owned).kind != "max":
		return _fail("MAX_STATE_FAILED")
	return true


func _quest(id: int, status: String, quest_type: String, quest_name: String) -> Dictionary:
	return {"id": 100 + id, "status": status, "quest": {"id": id, "name": quest_name, "quest_type": quest_type, "exp_reward": 120, "lumis_reward": 1500,
		"rewards": [{"item_name": "Red Potion", "quantity": 3}]},
		"objective_progress": [
			{"current_count": 3, "is_completed": status != "in_progress", "objective": {"objective_type": "DEFEAT_ENEMY", "enemy_name": "Slime", "defeat_count": 3}},
			{"current_count": 0, "is_completed": status != "in_progress", "objective": {"objective_type": "CLEAR_NORMAL_DUNGEON", "dungeon_name": null, "clear_count": 1}},
		]}


func _check_quest_rules() -> bool:
	var quests := [_quest(1, "claimed", "daily", "A"), _quest(2, "in_progress", "once", "B"), _quest(3, "completed", "weekly", "C"), _quest(4, "in_progress", "daily", "D")]
	var names := QuestRules.sorted(quests).map(func(q): return q.quest.name)
	if names != ["C", "D", "B", "A"]:
		return _fail("QUEST_SORT_FAILED %s" % [names])
	if QuestRules.ready_count(quests) != 1:
		return _fail("READY_COUNT_FAILED")
	if QuestRules.objective_text(quests[0].objective_progress[1].objective) != "Clear any dungeon":
		return _fail("OBJECTIVE_TEXT_FAILED")
	if QuestRules.rewards_text(quests[0].quest) != "120 EXP  •  1,500 Lumis  •  Red Potion ×3":
		return _fail("REWARDS_TEXT_FAILED %s" % QuestRules.rewards_text(quests[0].quest))
	if QuestRules.claimed_text({"rewards": {"exp": 120, "lumis": 0, "items": [{"name": "Red Potion", "quantity": 3}]}}) != "+120 EXP, Red Potion ×3":
		return _fail("CLAIMED_TEXT_FAILED")
	return true


func _check_world_rules() -> bool:
	var dungeons := AdventurePage._tagged([{"id": 1, "name": "Field", "order": 2}, {"id": 2, "name": "Cave", "order": 1}, {"id": 3, "name": "Lost", "order": 3}], "normal")
	var bosses := AdventurePage._tagged([{"id": 9, "name": "Golem", "order": 1}], "boss")
	var regions := AdventurePage.build_regions([
		{"id": 2, "name": "Peaks", "order": 2, "locations": [{"name": "Summit", "order": 1, "normal_dungeons": [], "boss_dungeons": [{"id": 9}]}]},
		{"id": 1, "name": "Meadow", "order": 1, "locations": [{"name": "Town", "order": 1, "normal_dungeons": [{"id": 1}, {"id": 2}], "boss_dungeons": []}]},
	], dungeons, bosses)
	var shape := regions.map(func(r): return "%s:%s" % [r.name, ",".join(r.locations[0].dungeons.map(func(d): return d.name))])
	if shape != ["Meadow:Field,Cave", "Peaks:Golem", "Elsewhere:Lost"]:
		return _fail("BUILD_REGIONS_FAILED %s" % [shape])
	if AdventurePage.build_regions([], dungeons, bosses)[0].name != "All dungeons":
		return _fail("FLAT_MAP_FAILED")
	var hero := {"id": 7, "level": 20}
	var boss := {"required_level": 15, "max_party_size": 2}
	if AdventurePage.boss_block_reason(boss, hero, null, false) != "":
		return _fail("BOSS_NO_PARTY_SHOULD_BE_ALLOWED")
	if not AdventurePage.boss_block_reason(boss, hero, {"leader_id": "8", "member_count": 2}, false).contains("leader"):
		return _fail("BOSS_LEADER_RULE_FAILED")
	if not AdventurePage.boss_block_reason(boss, hero, {"leader_id": "7", "member_count": 3}, false).contains("too big"):
		return _fail("BOSS_PARTY_SIZE_RULE_FAILED")
	if not AdventurePage.boss_block_reason(boss, {"id": 7, "level": 3}, null, false).contains("level 15"):
		return _fail("BOSS_LEVEL_RULE_FAILED")
	return true


func _check_skills_page() -> bool:
	var page := SkillsPage.new()
	add_child(page)
	page.load_skills()
	if not await _wait_for(func(): return not page._busy and page._skills.size() == 1):
		return _fail("SKILLS_LOAD_FAILED %s" % page._status.text)
	if page._learnable.size() != 1 or page.upgradable_count() != 1 or page._upgrade_button.disabled:
		return _fail("SKILLS_STATE_FAILED %s" % page._state.text)
	if not page._materials.get_child(0).get_child(1).text.begins_with("Slime Jelly"):
		return _fail("MATERIAL_NAME_FAILED")
	page._on_upgrade_pressed()
	if not await _wait_for(func(): return _posts.has("/api/characters/my/skills/11/upgrade/") and not page._busy and int(page._skills[0].level) == 3):
		return _fail("SKILL_UPGRADE_FAILED %s" % [_posts])
	page._select("learn:40")
	if page._upgrade_button.visible or not page._now_text.text.contains("level 12"):
		return _fail("LEARNABLE_DETAIL_FAILED")
	page.queue_free()
	return true


func _check_quests_page() -> bool:
	var page := QuestsPage.new()
	add_child(page)
	page.load_quests()
	if not await _wait_for(func(): return not page._busy and page._quests.size() == 2):
		return _fail("QUESTS_LOAD_FAILED %s" % page._status.text)
	if page._selected_id != "103" or page._claim_button.disabled:
		return _fail("QUEST_DEFAULT_PICK_FAILED %s" % page._selected_id)
	page._on_claim_pressed()
	if not await _wait_for(func(): return _posts.has("/api/quests/3/claim/") and not page._busy):
		return _fail("QUEST_CLAIM_FAILED %s" % [_posts])
	if not page._status.text.begins_with("Claimed: +120 EXP"):
		return _fail("QUEST_CLAIM_MESSAGE_FAILED %s" % page._status.text)
	page._set_filter("daily")
	if page._visible().size() != 1:
		return _fail("QUEST_FILTER_FAILED")
	page.queue_free()
	return true


func _check_adventure_page() -> bool:
	var page := AdventurePage.new()
	add_child(page)
	page.set_context({"id": 7, "name": "Hero", "level": 20}, 50, {})
	page.load_dungeons()
	if not await _wait_for(func(): return not page._busy and page._regions.size() == 2):
		return _fail("WORLD_LOAD_FAILED %s" % page._status.text)
	if page._regions_row.get_child_count() != 2:
		return _fail("REGION_CHIPS_FAILED")
	page._select_region("2")
	if str(page._selected.get("kind")) != "boss" or page._enter_button.text != "Challenge boss":
		return _fail("BOSS_SELECT_FAILED %s" % [page._selected])
	page._on_enter_pressed()
	if not await _wait_for(func(): return _posts.has("/api/world/boss-dungeons/9/enter/")):
		return _fail("BOSS_ENTER_FAILED %s" % [_posts])
	if _posts.find("/api/party/party/create_party/") != _posts.find("/api/world/boss-dungeons/9/enter/") - 1:
		return _fail("PARTY_NOT_CREATED_FIRST %s" % [_posts])
	return true


func _handle(path: String, head: String, _payload: Variant) -> Array:
	if head.begins_with("POST"):
		_posts.append(path)
		match path:
			"/api/characters/my/skills/11/upgrade/":
				_skill_level = 3
				return [200, {"detail": "Skill upgraded; current level is 3."}]
			"/api/quests/3/claim/":
				_quest_status = "claimed"
				return [200, {"success": true, "rewards": {"exp": 120, "lumis": 1500, "items": []}}]
			"/api/party/party/create_party/":
				return [201, {"id": 5, "leader_id": "7", "member_count": 1}]
			"/api/world/boss-dungeons/9/enter/":
				# The test stops here; a battle would open next.
				return [400, {"detail": "Stop."}]
		return [200, {}]
	match path:
		"/api/characters/my/":
			return [200, {"id": 7, "name": "Hero", "level": 9}]
		"/api/characters/my/skills/":
			return [200, [_skill(_skill_level, [{"item_template_id": 7, "quantity": 4}])]]
		"/api/skills/learnable/":
			return [200, [{"id": 40, "name": "Storm", "unlock_level": 12, "effect_type": "DAMAGE"}]]
		"/api/inventory/":
			return [200, {"count": 1, "next": null, "results": [{"id": 1, "quantity": 6, "template": {"id": 7, "name": "Slime Jelly"}}]}]
		"/api/items/templates/7/":
			return [200, {"id": 7, "name": "Slime Jelly"}]
		"/api/quests/":
			return [200, [_quest(3, _quest_status, "weekly", "Hunt"), _quest(4, "in_progress", "daily", "Patrol")]]
		"/api/world/normal-dungeons/":
			return [200, {"count": 1, "next": null, "results": [{"id": 1, "name": "Field", "order": 1, "required_level": 1, "stamina_cost": 5}]}]
		"/api/world/boss-dungeons/":
			return [200, {"count": 1, "next": null, "results": [{"id": 9, "name": "Golem", "order": 1, "required_level": 15, "max_party_size": 4, "time_type": "weekly"}]}]
		"/api/world/regions/":
			return [200, [
				{"id": 1, "name": "Meadow", "order": 1, "locations": [{"name": "Town", "order": 1, "normal_dungeons": [{"id": 1}], "boss_dungeons": []}]},
				{"id": 2, "name": "Peaks", "order": 2, "locations": [{"name": "Summit", "order": 1, "normal_dungeons": [], "boss_dungeons": [{"id": 9}]}]},
			]]
	return [404, {"detail": "Not found."}]


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
