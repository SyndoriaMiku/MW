class_name HubScreen
extends Control

## The main menu after login. A header with the character and stamina, a
## content box that shows the selected destination, and the navigation bar.
## Pages keep their state while the player moves between them and reload when
## shown again. Back (Escape or the mouse back button) returns to the previous
## page, playing the entry transition in reverse.

const SLIDE := 28.0
const HISTORY_LIMIT := 20
const DESTINATIONS := [
	{"id": "home", "label": "Home", "icon": "home"},
	{"id": "adventure", "label": "Adventure", "icon": "swords"},
	{"id": "quests", "label": "Quests", "icon": "task_alt"},
	{"id": "character", "label": "Character", "icon": "person"},
	{"id": "skills", "label": "Skills", "icon": "menu_book"},
	{"id": "inventory", "label": "Inventory", "icon": "backpack"},
	{"id": "enhance", "label": "Enhance", "icon": "auto_awesome"},
	{"id": "shop", "label": "Shop", "icon": "storefront"},
	{"id": "settings", "label": "Settings", "icon": "settings"},
]

@onready var avatar: PanelContainer = %Avatar
@onready var avatar_initials: Label = %AvatarInitials
@onready var character_name: Label = %CharacterName
@onready var character_details: Label = %CharacterDetails
@onready var lumis_label: Label = %LumisLabel
@onready var nova_label: Label = %NovaLabel
@onready var stamina_box: PanelContainer = %StaminaBox
@onready var stamina_label: Label = %StaminaLabel
@onready var stamina_bar: StaminaBar = %StaminaBar
@onready var stamina_hint: Label = %StaminaHint
@onready var content_box: PanelContainer = %ContentBox
@onready var pages_root: Control = %Pages
@onready var nav_bar: NavBar = %NavBar
@onready var loading_label: Label = %LoadingLabel

## Page id -> the node shown in the content box (a ScrollContainer around
## embedded screens).
var _pages: Dictionary = {}
## Page id -> the page itself (the embedded screen for screen pages).
var _screens: Dictionary = {}
var _current := ""
var _history: Array[String] = []
var _character: Dictionary = {}
var _profile: Dictionary = {}
var _active_battle: Dictionary = {}
var _events: Array = []
var _quest_counts := [0, 0]
var _quests_refresh_queued := false
var _server_offset := 0.0
var _stamina := StaminaClock.new()
var _tween: Tween
var _ready_to_navigate := false
var _header_refresh_queued := false


func _ready() -> void:
	avatar.add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER_HIGHEST, M3.CORNER_CARD, 0.0))
	stamina_box.add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER_HIGH, M3.CORNER_EXTRA_LARGE, 0.0))
	content_box.add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER_HIGH, M3.CORNER_EXTRA_LARGE, 0.0))
	# Pages are clipped to the box's rounded corners.
	content_box.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	%LumisIcon.add_child(M3.icon_label("paid", 18, M3.GOLD))
	%NovaIcon.add_child(M3.icon_label("diamond", 18, M3.EPIC))
	%StaminaIcon.add_child(M3.icon_label("bolt", 26, M3.PRIMARY))
	nav_bar.setup(DESTINATIONS)
	GameCache.invalidated.connect(_on_cache_invalidated)
	nav_bar.destination_selected.connect(func(id): open_page(id))
	var timer := Timer.new()
	timer.wait_time = 1.0
	timer.autostart = true
	timer.timeout.connect(_render_stamina)
	add_child(timer)
	if not SceneRouter.require_session():
		return
	var args := SceneRouter.take_args()
	await _load_bootstrap()
	if not is_inside_tree():
		return
	_ready_to_navigate = true
	open_page(str(args.get("page", "home")), args.get("page_args", {}), false)
	_refresh_quest_badge()


func _unhandled_input(event: InputEvent) -> void:
	var back_pressed := event.is_action_pressed("ui_cancel")
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_XBUTTON1:
		back_pressed = true
	if back_pressed and go_back():
		get_viewport().set_input_as_handled()


func current_page() -> String:
	return _current


func page(id: String) -> Control:
	return _screens.get(id)


## Shows destination `id`. `args` go to the page (e.g. {"tab": "aurora"} for
## Enhance). Opening the current page again only applies the args.
func open_page(id: String, args: Dictionary = {}, animate: bool = true) -> void:
	if not _ready_to_navigate or not _is_destination(id):
		return
	if id == _current:
		_hand_args(_screens[id], args)
		return
	if not _current.is_empty():
		_history.append(_current)
		if _history.size() > HISTORY_LIMIT:
			_history.pop_front()
	_show(id, args, animate, false)


## Returns to the previous page; false when there is none.
func go_back() -> bool:
	if _history.is_empty() or not _ready_to_navigate:
		return false
	_show(_history.pop_back(), {}, true, true)
	return true


func _show(id: String, args: Dictionary, animate: bool, backwards: bool) -> void:
	var outgoing: Control = _pages.get(_current)
	var created := not _pages.has(id)
	var incoming := _page_for(id, args)
	_current = id
	nav_bar.select(id, animate)
	if not created:
		_on_page_shown(id, _screens[id], args)
	_transition(outgoing, incoming, animate, backwards)
	if outgoing != null:
		_refresh_header()


func _page_for(id: String, args: Dictionary) -> Control:
	if _pages.has(id):
		return _pages[id]
	var created: Control
	var host: Control = null
	match id:
		"home":
			var home := HomePage.new()
			home.adventure_requested.connect(open_page.bind("adventure"))
			home.resume_requested.connect(func(): SceneRouter.go_to(SceneRouter.BATTLE))
			home.quests_requested.connect(open_page.bind("quests"))
			created = home
		"quests":
			var quests := QuestsPage.new()
			quests.quests_changed.connect(func(_ready_count): _refresh_quest_badge())
			created = quests
		"skills":
			created = SkillsPage.new()
		"adventure":
			var adventure := AdventurePage.new()
			adventure.stamina_changed.connect(_refresh_header)
			created = adventure
		"settings":
			created = _build_settings_page()
		_:
			SceneRouter.hand_args(args)
			created = load(SceneRouter.HUB_SCENES[id]).instantiate()
			created.set_meta("embedded", true)
			host = _scroll_host(created)
	created.name = id.capitalize().replace(" ", "") + "Page"
	if host == null:
		host = created
		host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	host.visible = false
	pages_root.add_child(host)
	_pages[id] = host
	_screens[id] = created
	_on_page_created(id, created)
	return host


## Screens were laid out for the whole window; in the content box they fill
## the space and scroll when they need more height than it has.
func _scroll_host(screen: Control) -> ScrollContainer:
	var scroll := ScrollContainer.new()
	scroll.name = "Scroll"
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	screen.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.add_child(screen)
	screen.ready.connect(func():
		var margin: Control = screen.get_node_or_null("Margin")
		if margin == null:
			return
		var fit := func(): screen.custom_minimum_size.y = margin.get_combined_minimum_size().y
		margin.minimum_size_changed.connect(fit)
		fit.call()
	, CONNECT_ONE_SHOT)
	return scroll


func _on_page_created(id: String, created: Control) -> void:
	match id:
		"home":
			_render_home()
		"adventure":
			created.set_context(_character, _stamina.value_at(_now()), _active_battle)
			created.load_dungeons()
		"quests":
			created.load_quests()
		"skills":
			created.load_skills()


func _on_page_shown(id: String, shown: Control, args: Dictionary) -> void:
	match id:
		"home":
			_render_home()
		"adventure":
			shown.set_context(_character, _stamina.value_at(_now()), _active_battle)
			shown.load_dungeons()
		"quests":
			shown.load_quests()
		"skills":
			shown.load_skills()
		"settings":
			pass
		_:
			if not args.is_empty() and shown.has_method("apply_args"):
				shown.apply_args(args)
			elif shown.has_method("reload_page"):
				shown.reload_page()


func _hand_args(target: Control, args: Dictionary) -> void:
	if not args.is_empty() and target.has_method("apply_args"):
		target.apply_args(args)


## Entering slides the page up and fades it in; going back plays that in
## reverse on the page being left.
func _transition(outgoing: Control, incoming: Control, animate: bool, backwards: bool) -> void:
	if _tween:
		_tween.kill()
		for child in pages_root.get_children():
			if child != incoming and child != outgoing:
				child.visible = false
			child.modulate.a = 1.0
			child.position = Vector2.ZERO
	incoming.visible = true
	if outgoing == null or outgoing == incoming or not animate:
		if outgoing != null and outgoing != incoming:
			outgoing.visible = false
		incoming.modulate.a = 1.0
		incoming.position = Vector2.ZERO
		return
	_tween = create_tween().set_parallel(true)
	M3.ease_tween(_tween)
	if backwards:
		pages_root.move_child(outgoing, -1)
		incoming.position = Vector2.ZERO
		incoming.modulate.a = 1.0
		_tween.tween_property(outgoing, "position", Vector2(0, SLIDE), M3.DURATION_MEDIUM)
		_tween.tween_property(outgoing, "modulate:a", 0.0, M3.DURATION_MEDIUM)
	else:
		pages_root.move_child(incoming, -1)
		incoming.position = Vector2(0, SLIDE)
		incoming.modulate.a = 0.0
		_tween.tween_property(incoming, "position", Vector2.ZERO, M3.DURATION_MEDIUM)
		_tween.tween_property(incoming, "modulate:a", 1.0, M3.DURATION_MEDIUM)
		_tween.tween_property(outgoing, "modulate:a", 0.0, M3.DURATION_SHORT)
	_tween.chain().tween_callback(func():
		outgoing.visible = false
		outgoing.position = Vector2.ZERO
		outgoing.modulate.a = 1.0
	)


func _load_bootstrap() -> void:
	loading_label.text = "Loading your adventure..."
	loading_label.visible = true
	var response: Dictionary = await ApiClient.get_json("session/bootstrap/")
	if not is_inside_tree():
		return
	if not response.get("ok", false):
		loading_label.text = ApiClient.error_message(response, "Unable to reach the server.")
		await _load_fallback()
		return
	var data: Dictionary = response.get("data", {})
	if data.get("character") == null:
		SceneRouter.go_to(SceneRouter.CHARACTER_CREATE)
		return
	var server_time := StaminaClock.iso_to_unix(str(data.get("server_time", "")))
	_server_offset = server_time - Time.get_unix_time_from_system() if server_time > 0.0 else 0.0
	_profile = data.get("profile", {}) if data.get("profile") is Dictionary else {}
	_set_character(data.get("character", {}))
	_set_active_battle(data.get("active_battle"))
	# Pages read these through GameCache, so they need not ask again.
	GameCache.store("characters/my/", _character)
	GameCache.store("users/profile/", _profile)
	GameCache.store("battles/active/", data.get("active_battle") if data.get("active_battle") is Dictionary else {})
	_events = data.get("rate_events", []) if data.get("rate_events") is Array else []
	loading_label.visible = false


## Older servers without session/bootstrap/.
func _load_fallback() -> void:
	var character_response: Dictionary = await GameCache.get_json("characters/my/")
	if int(character_response.get("status", 0)) == 404:
		SceneRouter.go_to(SceneRouter.CHARACTER_CREATE)
		return
	if not character_response.get("ok", false):
		return
	_set_character(character_response.get("data", {}))
	var profile_response: Dictionary = await GameCache.get_json("users/profile/")
	if profile_response.get("ok", false):
		_profile = profile_response.data
	var battle_response: Dictionary = await GameCache.get_json("battles/active/")
	if battle_response.get("ok", false):
		_set_active_battle(battle_response.data)
	_render_header()
	loading_label.visible = false


## A POST changed player data: refresh the header once, after the page that
## made the change has had its turn.
func _on_cache_invalidated(paths: Array) -> void:
	if (paths.has("*") or paths.any(func(path): return str(path).begins_with("quests/"))) and not _quests_refresh_queued and _ready_to_navigate:
		_quests_refresh_queued = true
		_refresh_quest_badge.call_deferred()
	for path in paths:
		if path == "*" or str(path).begins_with("characters/") or str(path).begins_with("users/") or str(path).begins_with("battles/"):
			if not _header_refresh_queued and _ready_to_navigate:
				_header_refresh_queued = true
				_queued_header_refresh.call_deferred()
			return


## Quests waiting to be claimed: a badge on Quests and the card on Home.
func _refresh_quest_badge() -> void:
	_quests_refresh_queued = false
	var response: Dictionary = await GameCache.get_json("quests/")
	if not is_inside_tree() or not response.get("ok", false):
		return
	var quests := ApiClient.unwrap_list(response.data)
	var ready := QuestRules.ready_count(quests)
	var active := quests.filter(func(quest): return str(quest.get("status")) == "in_progress").size()
	_quest_counts = [ready, active]
	nav_bar.set_badge("quests", ready)
	var home: HomePage = _screens.get("home")
	if home != null:
		home.set_quests(ready, active)


func _queued_header_refresh() -> void:
	_header_refresh_queued = false
	await _refresh_header()


## Re-reads the character and currencies (from GameCache, so only what a POST
## changed reaches the server).
func _refresh_header() -> void:
	var character_response: Dictionary = await GameCache.get_json("characters/my/")
	if not is_inside_tree():
		return
	if character_response.get("ok", false):
		_set_character(character_response.data)
	var profile_response: Dictionary = await GameCache.get_json("users/profile/")
	if not is_inside_tree():
		return
	if profile_response.get("ok", false):
		_profile = profile_response.data
	var battle_response: Dictionary = await GameCache.get_json("battles/active/")
	if not is_inside_tree():
		return
	if battle_response.get("ok", false):
		_set_active_battle(battle_response.data)
	_render_header()
	if _current == "home":
		_render_home()


func _set_character(character: Dictionary) -> void:
	_character = character
	SessionStore.character = character
	_stamina = StaminaClock.from_character(character)
	_render_header()


func _set_active_battle(battle: Variant) -> void:
	_active_battle = {}
	SessionStore.active_battle_id = ""
	if battle is Dictionary and str(battle.get("status", "in_progress")) == "in_progress":
		var combat_id := ApiClient.id_string(battle.get("id"))
		if not combat_id.is_empty():
			_active_battle = battle
			SessionStore.active_battle_id = combat_id


func _render_header() -> void:
	var display_name := str(_character.get("name", SessionStore.username))
	character_name.text = display_name
	avatar_initials.text = initials(display_name)
	var level := int(_character.get("level", 1))
	var required := int(_character.get("required_exp", 0))
	var exp_text := "  •  EXP %d%%" % int(100.0 * int(_character.get("current_exp", 0)) / required) if required > 0 else ""
	character_details.text = "Lv. %d%s" % [level, exp_text]
	lumis_label.text = group_digits(int(_profile.get("lumis", 0)))
	nova_label.text = group_digits(int(_profile.get("nova", 0)))
	_render_stamina(false)


func _render_stamina(animate: bool = true) -> void:
	if _character.is_empty():
		return
	var now := _now()
	var value := _stamina.value_at(now)
	stamina_label.text = "Stamina %d/%d" % [value, _stamina.maximum]
	stamina_bar.set_value(value, _stamina.maximum, animate)
	if value >= _stamina.maximum:
		stamina_hint.text = "Full"
	else:
		stamina_hint.text = "+1 in %s   •   full in %s" % [
			StaminaClock.duration_text(_stamina.seconds_to_next(now)),
			StaminaClock.duration_text(_stamina.seconds_to_full(now)),
		]


func _render_home() -> void:
	var home: HomePage = _screens.get("home")
	if home == null:
		return
	home.set_character_name(str(_character.get("name", "")))
	home.set_active_battle(_active_battle)
	home.set_events(_events, _server_offset)
	home.set_quests(_quest_counts[0], _quest_counts[1])


func _build_settings_page() -> Control:
	var panel: SettingsPanel = SettingsPanel.SCENE.instantiate()
	panel.set_meta("embedded", true)
	panel.ready.connect(func(): panel.add_account_section(SessionStore.username, _on_sign_out), CONNECT_ONE_SHOT)
	return panel


func _on_sign_out() -> void:
	_ready_to_navigate = false
	await SessionStore.logout()
	SceneRouter.go_to(SceneRouter.LOGIN)


func _now() -> float:
	return Time.get_unix_time_from_system() + _server_offset


func _is_destination(id: String) -> bool:
	for entry in DESTINATIONS:
		if entry.id == id:
			return true
	return false


static func initials(text: String) -> String:
	var result := ""
	for word in text.split(" ", false):
		result += word.left(1).to_upper()
	return result.left(2) if not result.is_empty() else "?"


## 1234567 -> "1,234,567".
static func group_digits(value: int) -> String:
	var digits := str(absi(value))
	var grouped := ""
	while digits.length() > 3:
		grouped = "," + digits.right(3) + grouped
		digits = digits.left(-3)
	return ("-" if value < 0 else "") + digits + grouped
