class_name QuestsPage
extends Control

## The character's quests with their objectives and rewards. Completed quests
## are claimed here; the list can be narrowed to daily, weekly or story quests.

signal quests_changed(ready_count: int)

const FILTERS := [["all", "All"], ["daily", "Daily"], ["weekly", "Weekly"], ["once", "Story"]]

var _quests: Array = []
var _filter := "all"
var _selected_id := ""
var _busy := false

var _status: Label
var _list: VBoxContainer
var _detail: VBoxContainer
var _filter_group := ButtonGroup.new()
var _name := Label.new()
var _chips := HBoxContainer.new()
var _description := Label.new()
var _objectives := VBoxContainer.new()
var _rewards := Label.new()
var _state := Label.new()
var _claim_button := Button.new()
var _empty := Label.new()


func _init() -> void:
	name = "QuestsPage"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var column := HubWidgets.page_column(self)
	var header := HubWidgets.header("Quests", load_quests)
	_status = header.status
	column.add_child(header.row)
	var filters := HBoxContainer.new()
	filters.add_theme_constant_override("separation", 8)
	header.row.add_child(filters)
	header.row.move_child(filters, 1)
	for entry in FILTERS:
		var chip := Button.new()
		chip.name = "Filter" + str(entry[1])
		chip.text = entry[1]
		chip.toggle_mode = true
		chip.button_group = _filter_group
		chip.theme_type_variation = &"ChipButton"
		chip.button_pressed = entry[0] == _filter
		chip.focus_mode = Control.FOCUS_NONE
		chip.pressed.connect(_set_filter.bind(entry[0]))
		filters.add_child(chip)
	var content := HBoxContainer.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 16)
	column.add_child(content)
	_list = HubWidgets.scroll_list(content, 420)
	_empty.theme_type_variation = &"MutedLabel"
	_empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail = HubWidgets.detail_card(content)
	_build_detail()


## The empty-state label is out of the tree while the list has rows.
func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and is_instance_valid(_empty) and _empty.get_parent() == null:
		_empty.free()


func _build_detail() -> void:
	_name.add_theme_font_size_override("font_size", M3.HEADLINE_MEDIUM)
	_name.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_name)
	_chips.add_theme_constant_override("separation", 8)
	_detail.add_child(_chips)
	_description.theme_type_variation = &"MutedLabel"
	_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_description)
	_detail.add_child(HubWidgets.section_label("Objectives"))
	_objectives.add_theme_constant_override("separation", 10)
	_detail.add_child(_objectives)
	_detail.add_child(HubWidgets.section_label("Rewards"))
	_rewards.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_child(_rewards)
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_child(spacer)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 12)
	_detail.add_child(actions)
	_state.theme_type_variation = &"MutedLabel"
	_state.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_state.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_state.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	actions.add_child(_state)
	_claim_button.name = "ClaimButton"
	_claim_button.text = "Claim rewards"
	_claim_button.theme_type_variation = &"PrimaryButton"
	_claim_button.custom_minimum_size = Vector2(200, 48)
	_claim_button.icon = IconTexture.make("redeem", M3.ON_PRIMARY)
	_claim_button.pressed.connect(_on_claim_pressed)
	actions.add_child(_claim_button)


## Called by the hub when the page is created or shown again.
func load_quests() -> void:
	if _busy:
		return
	_set_busy(true, "Loading quests...")
	var response: Dictionary = await GameCache.get_json("quests/")
	if not is_inside_tree():
		return
	if not response.get("ok", false):
		_set_busy(false, ApiClient.error_message(response, "Unable to load quests."))
		return
	_quests = QuestRules.sorted(ApiClient.unwrap_list(response.data))
	var visible_quests := _visible()
	if _find(_selected_id).is_empty() or not visible_quests.has(_find(_selected_id)):
		_selected_id = _id(visible_quests[0]) if not visible_quests.is_empty() else ""
	_set_busy(false, "")
	_render()
	quests_changed.emit(QuestRules.ready_count(_quests))


func ready_count() -> int:
	return QuestRules.ready_count(_quests)


func _visible() -> Array:
	if _filter == "all":
		return _quests
	return _quests.filter(func(quest): return str(quest.get("quest", {}).get("quest_type")) == _filter)


func _set_filter(value: String) -> void:
	_filter = value
	var visible_quests := _visible()
	if not visible_quests.has(_find(_selected_id)):
		_selected_id = _id(visible_quests[0]) if not visible_quests.is_empty() else ""
	_render()


func _render() -> void:
	HubWidgets.clear(_list, [_empty])
	var visible_quests := _visible()
	if visible_quests.is_empty():
		_empty.text = "No quests right now. New ones appear as you level up." if _quests.is_empty() else "No quests of this kind."
		_list.add_child(_empty)
	for quest in visible_quests:
		var template: Dictionary = quest.get("quest", {})
		var tally := QuestRules.objective_tally(quest)
		var status := str(quest.get("status", ""))
		var progress: Array = quest.get("objective_progress", [])
		var counted := "%d/%d" % tally
		if progress.size() == 1:
			# One objective: show its count rather than "0/1".
			var target := QuestRules.objective_target(progress[0].get("objective", {}))
			counted = "%d/%d" % [mini(int(progress[0].get("current_count", 0)), target), target]
		var tag_text: String = {"completed": "Ready", "claimed": "Claimed"}.get(status, counted)
		var tag_color: Color = {"completed": M3.SUCCESS, "claimed": M3.ON_SURFACE_VARIANT}.get(status, M3.PRIMARY)
		var card := HubWidgets.list_card(
			"task_alt" if status != "in_progress" else "assignment",
			str(template.get("name", "Quest")),
			"%s  •  %s" % [QuestRules.TYPE_LABELS.get(str(template.get("quest_type")), "Quest"), QuestRules.rewards_text(template)],
			_id(quest) == _selected_id, status == "claimed", tag_text, tag_color
		)
		card.pressed.connect(_select.bind(_id(quest)))
		_list.add_child(card)
	_render_detail()


func _render_detail() -> void:
	var quest := _find(_selected_id)
	_detail.get_parent().visible = not quest.is_empty()
	if quest.is_empty():
		return
	var template: Dictionary = quest.get("quest", {})
	var status := str(quest.get("status", ""))
	_name.text = str(template.get("name", "Quest"))
	HubWidgets.clear(_chips)
	_chips.add_child(HubWidgets.chip("flag", QuestRules.TYPE_LABELS.get(str(template.get("quest_type")), "Quest")).chip)
	_chips.add_child(HubWidgets.chip("schedule", QuestRules.reset_text(str(template.get("quest_type")))).chip)
	_description.text = str(template.get("description", "")).strip_edges()
	_description.visible = not _description.text.is_empty()
	HubWidgets.clear(_objectives)
	var progress: Array = quest.get("objective_progress", [])
	if progress.is_empty():
		var none := Label.new()
		none.text = "Nothing to do — just claim it."
		none.theme_type_variation = &"MutedLabel"
		_objectives.add_child(none)
	for entry in progress:
		_objectives.add_child(_objective_row(entry, status == "claimed"))
	_rewards.text = QuestRules.rewards_text(template)
	match status:
		"completed":
			_state.text = "All objectives done."
		"claimed":
			_state.text = "Rewards claimed. %s" % ("Comes back after the reset." if str(template.get("quest_type")) != "once" else "")
		_:
			var tally := QuestRules.objective_tally(quest)
			_state.text = "%d of %d objectives done." % tally
	_claim_button.visible = status != "claimed"
	_claim_button.disabled = _busy or status != "completed"


func _objective_row(entry: Dictionary, claimed: bool) -> Control:
	var objective: Dictionary = entry.get("objective", {})
	var target := QuestRules.objective_target(objective)
	var current := mini(int(entry.get("current_count", 0)), target)
	var done := bool(entry.get("is_completed", false)) or claimed
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	box.add_child(row)
	row.add_child(M3.icon_label("check_circle" if done else "radio_button_unchecked", 18, M3.SUCCESS if done else M3.ON_SURFACE_VARIANT))
	var label := Label.new()
	label.text = QuestRules.objective_text(objective)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(label)
	var count := Label.new()
	count.text = "%d / %d" % [target if claimed else current, target]
	count.theme_type_variation = &"SuccessLabel" if done else &"MutedLabel"
	row.add_child(count)
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(0, 6)
	bar.show_percentage = false
	bar.max_value = target
	bar.value = target if claimed else current
	box.add_child(bar)
	return box


func _select(id: String) -> void:
	_selected_id = id
	_render()


func _on_claim_pressed() -> void:
	var quest := _find(_selected_id)
	if _busy or quest.is_empty() or str(quest.get("status")) != "completed":
		return
	var template: Dictionary = quest.get("quest", {})
	_set_busy(true, "Claiming %s..." % str(template.get("name", "the quest")))
	var response: Dictionary = await ApiClient.post_json("quests/%s/claim/" % ApiClient.id_string(template.get("id")))
	if not is_inside_tree():
		return
	var message: String
	if response.get("ok", false):
		var gained := QuestRules.claimed_text(response.data)
		message = "Claimed: %s" % gained if not gained.is_empty() else "Rewards claimed."
	else:
		message = ApiClient.error_message(response, "Unable to claim the rewards.")
	_busy = false
	await load_quests()
	_status.text = message


func _set_busy(value: bool, message: String) -> void:
	_busy = value
	_status.text = message
	if not _quests.is_empty():
		_render_detail()


func _find(id: String) -> Dictionary:
	for quest in _quests:
		if _id(quest) == id:
			return quest
	return {}


static func _id(quest: Dictionary) -> String:
	return ApiClient.id_string(quest.get("id"))
