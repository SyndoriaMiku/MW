class_name QuestRules
extends RefCounted

## How the Quests page reads the backend's character quests: objective text
## and progress, ordering, rewards. A quest is "completed" when every objective
## is done and its rewards wait to be claimed; daily and weekly quests reset
## on the server's calendar.

const TYPE_LABELS := {"daily": "Daily", "weekly": "Weekly", "once": "Story"}
const STATUS_ORDER := {"completed": 0, "in_progress": 1, "claimed": 2}
const TYPE_ORDER := {"daily": 0, "weekly": 1, "once": 2}


## "Defeat Slime", "Collect Red Potion", "Clear any dungeon"...
static func objective_text(objective: Dictionary) -> String:
	match str(objective.get("objective_type", "")):
		"DEFEAT_ENEMY":
			return "Defeat %s" % _name_or(objective.get("enemy_name"), "any enemy")
		"COLLECT_ITEM":
			return "Collect %s" % _name_or(objective.get("item_name"), "items")
		"CLEAR_NORMAL_DUNGEON":
			return "Clear %s" % _name_or(objective.get("dungeon_name"), "any dungeon")
		"CLEAR_BOSS_DUNGEON":
			return "Defeat the boss of %s" % _name_or(objective.get("boss_dungeon_name"), "any boss dungeon")
	return "Objective"


static func objective_target(objective: Dictionary) -> int:
	for key in ["defeat_count", "collect_count", "clear_count", "boss_clear_count"]:
		if int(objective.get(key, 0)) > 0:
			return int(objective.get(key))
	return 1


## [done, total] objectives of a character quest.
static func objective_tally(character_quest: Dictionary) -> Array:
	var done := 0
	var progress: Array = character_quest.get("objective_progress", [])
	for entry in progress:
		if bool(entry.get("is_completed", false)):
			done += 1
	return [done, progress.size()]


## Ready to claim first, then in progress, then claimed; daily, weekly, story.
static func sorted(quests: Array) -> Array:
	var result := quests.duplicate()
	result.sort_custom(func(a, b):
		var left := [int(STATUS_ORDER.get(str(a.get("status")), 3)), int(TYPE_ORDER.get(str(a.get("quest", {}).get("quest_type")), 3)), str(a.get("quest", {}).get("name", ""))]
		var right := [int(STATUS_ORDER.get(str(b.get("status")), 3)), int(TYPE_ORDER.get(str(b.get("quest", {}).get("quest_type")), 3)), str(b.get("quest", {}).get("name", ""))]
		return left < right
	)
	return result


static func ready_count(quests: Array) -> int:
	return quests.filter(func(quest): return str(quest.get("status")) == "completed").size()


## "120 EXP  •  50 Lumis  •  Red Potion ×3".
static func rewards_text(quest: Dictionary) -> String:
	var parts: Array[String] = []
	if int(quest.get("exp_reward", 0)) > 0:
		parts.append("%d EXP" % int(quest.exp_reward))
	if int(quest.get("lumis_reward", 0)) > 0:
		parts.append("%s Lumis" % HubScreen.group_digits(int(quest.lumis_reward)))
	for reward in quest.get("rewards", []):
		parts.append("%s ×%d" % [str(reward.get("item_name", "Item")), int(reward.get("quantity", 1))])
	return "  •  ".join(parts) if not parts.is_empty() else "No reward"


## What a claim response gave: "+120 EXP, +50 Lumis, Red Potion ×3".
static func claimed_text(response_data: Dictionary) -> String:
	var rewards: Dictionary = response_data.get("rewards", {}) if response_data.get("rewards") is Dictionary else {}
	var parts: Array[String] = []
	if int(rewards.get("exp", 0)) > 0:
		parts.append("+%d EXP" % int(rewards.exp))
	if int(rewards.get("lumis", 0)) > 0:
		parts.append("+%s Lumis" % HubScreen.group_digits(int(rewards.lumis)))
	for item in rewards.get("items", []):
		parts.append("%s ×%d" % [str(item.get("name", "Item")), int(item.get("quantity", 1))])
	return ", ".join(parts)


static func reset_text(quest_type: String) -> String:
	match quest_type:
		"daily":
			return "Resets every day"
		"weekly":
			return "Resets every Monday"
	return "One time"


static func _name_or(value: Variant, fallback: String) -> String:
	return str(value) if value != null and not str(value).is_empty() else fallback
