extends Control

@onready var username_input: LineEdit = %UsernameInput
@onready var password_input: LineEdit = %PasswordInput
@onready var login_button: Button = %LoginButton
@onready var error_label: Label = %ErrorLabel
@onready var loading_label: Label = %LoadingLabel
@onready var server_label: Label = %ServerLabel
@onready var create_account_button: Button = %CreateAccountButton
@onready var retry_server_button: Button = %RetryServerButton
@onready var settings_button: Button = %SettingsButton

const SERVER_OK_COLOR := M3.SUCCESS
const SERVER_WAIT_COLOR := M3.GOLD
const SERVER_DOWN_COLOR := M3.ERROR
## After this long without an answer the server is probably waking up.
const WAKE_HINT_DELAY := 4.0

var _checking_server := false


func _ready() -> void:
	login_button.pressed.connect(_on_login_pressed)
	retry_server_button.pressed.connect(_check_server)
	settings_button.pressed.connect(func(): SettingsPanel.open(self))
	create_account_button.pressed.connect(SceneRouter.go_to.bind(SceneRouter.REGISTER))
	username_input.text_submitted.connect(_focus_password)
	password_input.text_submitted.connect(_submit_from_password)
	username_input.grab_focus()
	await _check_server()


## Pings the backend so a sleeping (Render) server starts waking up while the
## player types, and shows whether it is reachable.
func _check_server() -> void:
	if _checking_server:
		return
	_checking_server = true
	retry_server_button.visible = false
	_show_server_status("connecting...", SERVER_WAIT_COLOR)
	get_tree().create_timer(WAKE_HINT_DELAY).timeout.connect(func():
		if _checking_server:
			_show_server_status("waking up the server, this can take up to a minute...", SERVER_WAIT_COLOR)
	)
	var online: bool = await ApiClient.ping()
	_checking_server = false
	if online:
		_show_server_status("online", SERVER_OK_COLOR)
	else:
		_show_server_status("unreachable", SERVER_DOWN_COLOR)
		retry_server_button.visible = true


func _show_server_status(status: String, color: Color) -> void:
	if not is_inside_tree():
		return
	server_label.text = "%s  •  %s" % [ApiClient.server_host(), status]
	server_label.add_theme_color_override("font_color", color)


func _focus_password(_value: String) -> void:
	password_input.grab_focus()


func _submit_from_password(_value: String) -> void:
	_on_login_pressed()


func _on_login_pressed() -> void:
	var username := username_input.text.strip_edges()
	var password := password_input.text
	if username.is_empty() or password.is_empty():
		_show_error("Please enter both username and password.")
		return

	_set_loading(true)
	var response: Dictionary = await ApiClient.post_json(
		"users/login/",
		{"username": username, "password": password}
	)
	if not response.get("ok", false):
		_set_loading(false)
		_show_error(ApiClient.error_message(response, "Login failed."))
		return

	var payload: Dictionary = response.get("data", {})
	var access := str(payload.get("access", ""))
	var refresh := str(payload.get("refresh", ""))
	if access.is_empty():
		_set_loading(false)
		_show_error("The server did not return an access token.")
		return

	SessionStore.begin_session(username, access, refresh)
	SceneRouter.go_to(SceneRouter.HUB)


func _set_loading(is_loading: bool) -> void:
	login_button.disabled = is_loading
	create_account_button.disabled = is_loading
	username_input.editable = not is_loading
	password_input.editable = not is_loading
	loading_label.visible = is_loading
	if is_loading:
		error_label.text = ""


func _show_error(message: String) -> void:
	error_label.text = message

