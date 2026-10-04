extends Control

## Character creation for an account without a character. The player picks a
## job (the class follows from it, and there is no job change later) and a name.

const MAIN_STAT_LABELS := {"str": "STR", "agi": "AGI", "int": "INT", "all": "ALL STATS"}

@onready var logout_button: Button = %LogoutButton
@onready var retry_button: Button = %RetryButton
@onready var job_list: VBoxContainer = %JobList
@onready var job_name: Label = %JobName
@onready var class_line: Label = %ClassLine
@onready var job_stats: Label = %JobStats
@onready var skill_list: Label = %SkillList
@onready var name_input: LineEdit = %NameInput
@onready var name_width: Label = %NameWidth
@onready var name_feedback: Label = %NameFeedback
@onready var form_error: Label = %FormError
@onready var create_button: Button = %CreateButton
@onready var status_label: Label = %StatusLabel

var _classes_by_id: Dictionary = {}
var _jobs: Array = []
var _selected_job: Dictionary = {}
var _skills_by_job: Dictionary = {}
var _job_buttons := ButtonGroup.new()
var _is_busy := false


func _ready() -> void:
	logout_button.pressed.connect(_on_logout_pressed)
	retry_button.pressed.connect(_load_catalog)
	name_input.text_changed.connect(_on_name_changed)
	name_input.text_submitted.connect(func(_value): _on_create_pressed())
	create_button.pressed.connect(_on_create_pressed)
	name_input.max_length = CharacterNameRules.MAX_WIDTH
	_on_name_changed("")
	_render_job_details()
	if not SceneRouter.require_session():
		return
	await _load_catalog()


func _load_catalog() -> void:
	_set_busy(true, "Loading jobs...")
	retry_button.visible = false

	# A player who already has a character belongs on the adventure board.
	var character_response: Dictionary = await GameCache.get_json("characters/my/")
	if character_response.get("ok", false):
		SessionStore.character = character_response.get("data", {})
		SceneRouter.go_to(SceneRouter.HUB)
		return

	var classes_response: Dictionary = await GameCache.get_all("classes/")
	var jobs_response: Dictionary = await GameCache.get_all("classes/jobs/")
	for response in [classes_response, jobs_response]:
		if not response.get("ok", false):
			retry_button.visible = true
			_set_busy(false, ApiClient.error_message(response, "Unable to load jobs."))
			return

	_classes_by_id.clear()
	for character_class in ApiClient.unwrap_list(classes_response.get("data", [])):
		_classes_by_id[ApiClient.id_string(character_class.get("id"))] = character_class
	set_jobs(ApiClient.unwrap_list(jobs_response.get("data", [])))
	if _jobs.is_empty():
		_set_busy(false, "No job is available yet. Ask an administrator to add one.")
		return
	_set_busy(false, "Choose a job and a name.")
	await _select_job(_jobs[0])


## Replaces the job list. Kept separate from loading so tests can feed it data.
func set_jobs(jobs: Array) -> void:
	_jobs = jobs.filter(func(job): return job is Dictionary)
	for child in job_list.get_children():
		child.queue_free()
	for job in _jobs:
		job_list.add_child(_create_job_button(job))


func _create_job_button(job: Dictionary) -> Button:
	var button := Button.new()
	button.toggle_mode = true
	button.theme_type_variation = &"ChipButton"
	button.button_group = _job_buttons
	button.custom_minimum_size = Vector2(0, 64)
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.text = "%s\n%s  •  %s" % [
		str(job.get("name", "Unknown Job")),
		_class_name(job),
		_main_stat_label(job),
	]
	button.pressed.connect(_select_job.bind(job))
	button.set_meta("job_id", ApiClient.id_string(job.get("id")))
	return button


func _select_job(job: Dictionary) -> void:
	_selected_job = job
	var job_id := ApiClient.id_string(job.get("id"))
	for button in job_list.get_children():
		button.set_pressed_no_signal(str(button.get_meta("job_id", "")) == job_id)
	form_error.text = ""
	_render_job_details()
	_refresh_create_button()
	if _skills_by_job.has(job_id):
		return

	skill_list.text = "Loading skills..."
	var response: Dictionary = await GameCache.get_all("skills/?job=%s" % job_id.uri_encode())
	if not response.get("ok", false):
		if ApiClient.id_string(_selected_job.get("id")) == job_id:
			skill_list.text = "Skills could not be loaded."
		return
	_skills_by_job[job_id] = ApiClient.unwrap_list(response.get("data", []))
	if ApiClient.id_string(_selected_job.get("id")) == job_id:
		_render_job_details()


func _render_job_details() -> void:
	if _selected_job.is_empty():
		job_name.text = "Choose a job"
		class_line.text = "Your job decides your class, weapons and skills."
		job_stats.text = ""
		skill_list.text = ""
		return

	var character_class: Dictionary = _classes_by_id.get(ApiClient.id_string(_selected_job.get("character_class")), {})
	job_name.text = str(_selected_job.get("name", "Unknown Job"))
	class_line.text = "%s class  •  Main stat %s" % [_class_name(_selected_job), _main_stat_label(_selected_job)]
	var weapon_type: Variant = _selected_job.get("weapon_type")
	job_stats.text = "HP  +%s per level     MP  +%s per level\nWeapon  %s     Main stat weight  ×%s" % [
		_plain_number(character_class.get("hp_growth", 0)),
		_plain_number(character_class.get("mp_growth", 0)),
		str(weapon_type).replace("_", " ").capitalize() if weapon_type != null and str(weapon_type) != "" else "Any",
		_plain_number(_selected_job.get("main_stat_weight", 1.0)),
	]
	var job_id := ApiClient.id_string(_selected_job.get("id"))
	if _skills_by_job.has(job_id):
		skill_list.text = format_skills(_skills_by_job[job_id])


## One line per player skill, in unlock order.
static func format_skills(skills: Array) -> String:
	var player_skills := skills.filter(func(skill):
		return skill is Dictionary and str(skill.get("availability", "PLAYER")) != "ENEMY"
	)
	player_skills.sort_custom(func(a, b): return int(a.get("required_level", 1)) < int(b.get("required_level", 1)))
	var lines := PackedStringArray()
	for skill in player_skills:
		var details := "Basic attack" if bool(skill.get("is_basic_attack", false)) else "MP %d  •  Cooldown %d" % [
			int(skill.get("mp_cost", 0)),
			int(skill.get("cooldown", 0)),
		]
		lines.append("Lv.%d   %s   —   %s" % [int(skill.get("required_level", 1)), str(skill.get("name", "Skill")), details])
	return "\n".join(lines) if not lines.is_empty() else "This job has no skills yet."


func _on_name_changed(_value: String) -> void:
	var name := name_input.text.strip_edges()
	var width := CharacterNameRules.width(name)
	name_width.text = "%s / %d" % ["?" if width < 0 else str(width), CharacterNameRules.MAX_WIDTH]
	var problem := CharacterNameRules.validate(name) if not name.is_empty() else ""
	name_feedback.text = problem if not problem.is_empty() else CharacterNameRules.RULE_MESSAGE
	name_feedback.add_theme_color_override("font_color", M3.ERROR if not problem.is_empty() else M3.ON_SURFACE_VARIANT)
	_refresh_create_button()


func _on_create_pressed() -> void:
	var name := name_input.text.strip_edges()
	if _is_busy or _selected_job.is_empty() or not CharacterNameRules.validate(name).is_empty():
		return
	form_error.text = ""
	_set_busy(true, "Creating %s..." % name)
	var response: Dictionary = await ApiClient.post_json(
		"characters/",
		{"name": name, "job": int(_selected_job.get("id", 0))}
	)
	if response.get("ok", false):
		SessionStore.character = response.get("data", {})
		SceneRouter.go_to(SceneRouter.HUB)
		return

	_set_busy(false, "The character was not created.")
	var field_errors := ApiClient.field_errors(response).duplicate()
	if field_errors.is_empty():
		var message := ApiClient.error_message(response, "Unable to create the character.")
		if message.contains("already has a character"):
			SceneRouter.go_to(SceneRouter.HUB)
			return
		form_error.text = message
		return
	if field_errors.has("name"):
		name_feedback.text = str(field_errors["name"])
		name_feedback.add_theme_color_override("font_color", M3.ERROR)
		name_input.grab_focus()
		field_errors.erase("name")
	form_error.text = "\n".join(PackedStringArray(field_errors.values()))


func _on_logout_pressed() -> void:
	_set_busy(true, "Signing out...")
	await SessionStore.logout()
	SceneRouter.go_to(SceneRouter.LOGIN)


func _refresh_create_button() -> void:
	var name_ok := CharacterNameRules.validate(name_input.text).is_empty()
	create_button.disabled = _is_busy or _selected_job.is_empty() or not name_ok


func _set_busy(value: bool, message: String) -> void:
	_is_busy = value
	logout_button.disabled = value
	name_input.editable = not value
	for button in job_list.get_children():
		button.disabled = value
	status_label.text = message
	_refresh_create_button()


func _class_name(job: Dictionary) -> String:
	var character_class: Dictionary = _classes_by_id.get(ApiClient.id_string(job.get("character_class")), {})
	return str(character_class.get("name", "Unknown"))


func _main_stat_label(job: Dictionary) -> String:
	var character_class: Dictionary = _classes_by_id.get(ApiClient.id_string(job.get("character_class")), {})
	var main_stat := str(character_class.get("main_stat", ""))
	return MAIN_STAT_LABELS.get(main_stat, main_stat.to_upper())


static func _plain_number(value: Variant) -> String:
	var number := float(value)
	return str(int(number)) if is_equal_approx(number, round(number)) else "%.2f" % number
