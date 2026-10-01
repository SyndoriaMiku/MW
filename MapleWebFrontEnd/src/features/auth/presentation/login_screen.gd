extends Control

@onready var username_input: LineEdit = %UsernameInput
@onready var password_input: LineEdit = %PasswordInput
@onready var login_button: Button = %LoginButton
@onready var error_label: Label = %ErrorLabel
@onready var loading_label: Label = %LoadingLabel
@onready var server_label: Label = %ServerLabel
@onready var create_account_button: Button = %CreateAccountButton


func _ready() -> void:
	server_label.text = ApiClient.server_host()
	login_button.pressed.connect(_on_login_pressed)
	create_account_button.pressed.connect(SceneRouter.go_to.bind(SceneRouter.REGISTER))
	username_input.text_submitted.connect(_focus_password)
	password_input.text_submitted.connect(_submit_from_password)
	username_input.grab_focus()


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
	SceneRouter.go_to(SceneRouter.LAUNCHER)


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

