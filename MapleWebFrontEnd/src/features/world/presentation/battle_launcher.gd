extends Control

@onready var player_name: Label = %PlayerName
@onready var player_details: Label = %PlayerDetails
@onready var stamina_label: Label = %StaminaLabel
@onready var active_battle_panel: PanelContainer = %ActiveBattlePanel
@onready var active_battle_details: Label = %ActiveBattleDetails
@onready var resume_button: Button = %ResumeButton
@onready var dungeon_picker: OptionButton = %DungeonPicker
@onready var dungeon_description: Label = %DungeonDescription
@onready var enter_button: Button = %EnterButton
@onready var refresh_button: Button = %RefreshButton
@onready var character_button: Button = %CharacterButton
@onready var inventory_button: Button = %InventoryButton
@onready var enhancement_button: Button = %EnhancementButton
@onready var logout_button: Button = %LogoutButton
@onready var status_label: Label = %StatusLabel

var _dungeons: Array = []
var _has_active_battle: bool = false


func _ready() -> void:
	enter_button.pressed.connect(_on_enter_pressed)
	resume_button.pressed.connect(_on_resume_pressed)
	refresh_button.pressed.connect(_load_screen_data)
	character_button.pressed.connect(_on_character_pressed)
	inventory_button.pressed.connect(_on_inventory_pressed)
	enhancement_button.pressed.connect(_on_enhancement_pressed)
	logout_button.pressed.connect(_on_logout_pressed)
	dungeon_picker.item_selected.connect(_on_dungeon_selected)
	if not SceneRouter.require_session():
		return
	await _load_screen_data()


func _load_screen_data() -> void:
	_set_loading(true, "Loading character and dungeons...")
	var character_response: Dictionary = await ApiClient.get_json("characters/my/")
	if not character_response.get("ok", false):
		_handle_api_error(character_response)
		return

	SessionStore.character = character_response.get("data", {})
	_render_character()
	await _load_active_battle()

	var dungeon_response: Dictionary = await ApiClient.get_json("world/normal-dungeons/")
	if not dungeon_response.get("ok", false):
		_handle_api_error(dungeon_response)
		return

	_dungeons = ApiClient.unwrap_list(dungeon_response.get("data", []))
	_render_dungeons()
	var ready_message := "Battle in progress — resume when ready." if _has_active_battle else "Connected to Django backend."
	_set_loading(false, ready_message)


func _load_active_battle() -> void:
	var response: Dictionary = await ApiClient.get_json("battles/active/")
	if not response.get("ok", false):
		_handle_api_error(response)
		return

	var battle: Dictionary = response.get("data", {})
	var combat_id := str(battle.get("id", ""))
	_has_active_battle = not combat_id.is_empty() and str(battle.get("status", "")) == "in_progress"
	active_battle_panel.visible = _has_active_battle
	if not _has_active_battle:
		SessionStore.active_battle_id = ""
		return

	SessionStore.active_battle_id = combat_id
	var phase := str(battle.get("turn_phase", "player_phase")).replace("_", " ").capitalize()
	active_battle_details.text = "Battle %s  •  Turn %d  •  %s" % [
		combat_id,
		int(battle.get("turn_count", 1)),
		phase,
	]


func _render_character() -> void:
	var character := SessionStore.character
	player_name.text = str(character.get("name", SessionStore.username))
	player_details.text = "Level %d  •  HP %d  •  MP %d  •  ATT %d" % [
		int(character.get("level", 1)),
		int(character.get("total_hp", character.get("base_hp", 0))),
		int(character.get("total_mp", character.get("base_mp", 0))),
		int(character.get("total_att", character.get("base_att", 0))),
	]
	stamina_label.text = "STAMINA  %d / %d" % [
		int(character.get("current_stamina", 0)),
		int(character.get("max_stamina", 0)),
	]


func _render_dungeons() -> void:
	dungeon_picker.clear()
	for dungeon in _dungeons:
		dungeon_picker.add_item(str(dungeon.get("name", "Unknown Dungeon")))
		dungeon_picker.set_item_metadata(dungeon_picker.item_count - 1, dungeon.get("id", 0))
	if _dungeons.is_empty():
		dungeon_description.text = "No normal dungeon is available."
		enter_button.disabled = true
	else:
		dungeon_picker.select(0)
		_on_dungeon_selected(0)


func _on_dungeon_selected(index: int) -> void:
	if index < 0 or index >= _dungeons.size():
		return
	var dungeon: Dictionary = _dungeons[index]
	dungeon_description.text = "%s\nRequired level %d  •  Stamina cost %d" % [
		str(dungeon.get("description", "Enter the dungeon and defeat every enemy.")),
		int(dungeon.get("required_level", 1)),
		int(dungeon.get("stamina_cost", 0)),
	]


func _on_enter_pressed() -> void:
	if _has_active_battle or dungeon_picker.selected < 0:
		return
	var dungeon_id: int = int(dungeon_picker.get_item_metadata(dungeon_picker.selected))
	_set_loading(true, "Entering dungeon...")
	var response: Dictionary = await ApiClient.post_json(
		"world/normal-dungeons/%d/enter/" % dungeon_id
	)
	if not response.get("ok", false):
		_handle_api_error(response)
		return

	SessionStore.active_battle_id = str(response.get("data", {}).get("combat_instance_id", ""))
	if SessionStore.active_battle_id.is_empty():
		_set_loading(false, "Server did not return a combat instance ID.")
		return
	SceneRouter.go_to(SceneRouter.BATTLE)


func _on_resume_pressed() -> void:
	if not _has_active_battle or SessionStore.active_battle_id.is_empty():
		return
	SceneRouter.go_to(SceneRouter.BATTLE)


func _on_logout_pressed() -> void:
	_set_loading(true, "Signing out...")
	logout_button.disabled = true
	await SessionStore.logout()
	SceneRouter.go_to(SceneRouter.LOGIN)


func _on_character_pressed() -> void:
	SceneRouter.go_to(SceneRouter.CHARACTER)


func _on_inventory_pressed() -> void:
	SceneRouter.go_to(SceneRouter.INVENTORY)


func _on_enhancement_pressed() -> void:
	SceneRouter.go_to(SceneRouter.ENHANCEMENT)


func _handle_api_error(response: Dictionary) -> void:
	_set_loading(false, ApiClient.error_message(response, "Unable to load game data."))


func _set_loading(is_loading: bool, message: String) -> void:
	enter_button.disabled = is_loading or _dungeons.is_empty() or _has_active_battle
	resume_button.disabled = is_loading or not _has_active_battle
	refresh_button.disabled = is_loading
	character_button.disabled = is_loading
	inventory_button.disabled = is_loading
	enhancement_button.disabled = is_loading
	dungeon_picker.disabled = is_loading
	status_label.text = message
