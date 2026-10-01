extends Node


func _ready() -> void:
	var packed: PackedScene = load("res://src/features/battle/presentation/battle_demo.tscn")
	if packed == null:
		printerr("BATTLE_SCENE_LOAD_FAILED")
		get_tree().quit(1)
		return
	var screen: Control = packed.instantiate()
	var state := BattleState.from_dict({
		"id": "test", "status": "in_progress", "turn_phase": "player_phase",
		"turn_count": 1, "current_player_position": 1,
		"combatants": [{
			"id": 1, "entity_id": "player", "name": "Tester", "is_player": true,
			"is_current_actor": true, "current_hp": 100, "current_mp": 20,
			"max_hp": 100, "max_mp": 20, "position": 1,
			"skills": [
				{"character_skill_id": 1, "name": "Normal Attack", "is_basic_attack": true, "can_use": true},
				{"character_skill_id": 2, "name": "Power Strike", "level": 1, "is_basic_attack": false, "can_use": false, "cooldown_remaining": 2, "mp_cost": 5, "target_type": "ENEMY", "damage_multiplier": 1.5},
			],
		}, {
			"id": 2, "entity_id": "enemy", "name": "Dummy", "is_player": false,
			"current_hp": 50, "current_mp": 0, "max_hp": 50, "max_mp": 1, "position": 2,
		}],
	})
	screen._battle = state
	var skills: Array = screen._selectable_skills()
	if skills.size() != 1 or str(skills[0].get("name", "")) != "Power Strike":
		printerr("BASIC_ATTACK_FILTER_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	var text: String = screen._skill_button_text(skills[0])
	if text.find("CD 2 TURNS") < 0:
		printerr("SKILL_COOLDOWN_LABEL_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	screen._setup_skill_popup()
	screen._render_skill_list()
	var skill_button: Button = screen._skill_list.get_child(0)
	if not skill_button.disabled:
		printerr("SKILL_COOLDOWN_DISABLED_STATE_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	print("BATTLE_SKILL_UI_OK selectable=%d label=%s" % [skills.size(), text.replace("\n", " | ")])
	screen.free()
	get_tree().quit(0)
