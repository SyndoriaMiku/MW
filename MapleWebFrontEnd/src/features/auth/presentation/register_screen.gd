extends Control

## Account sign-up. The backend logs the new account in, so a successful sign-up
## goes straight to character creation.

const USERNAME_PATTERN := "^[A-Za-z0-9_-]{3,20}$"
const MIN_PASSWORD_LENGTH := 8

@onready var username_input: LineEdit = %UsernameInput
@onready var username_error: Label = %UsernameError
@onready var email_input: LineEdit = %EmailInput
@onready var email_error: Label = %EmailError
@onready var password_input: LineEdit = %PasswordInput
@onready var password_error: Label = %PasswordError
@onready var confirm_input: LineEdit = %ConfirmInput
@onready var confirm_error: Label = %ConfirmError
@onready var form_error: Label = %FormError
@onready var register_button: Button = %RegisterButton
@onready var back_button: Button = %BackButton
@onready var loading_label: Label = %LoadingLabel

var _username_regex := RegEx.create_from_string(USERNAME_PATTERN)
var _is_submitting := false


func _ready() -> void:
	register_button.pressed.connect(_on_register_pressed)
	back_button.pressed.connect(SceneRouter.go_to.bind(SceneRouter.LOGIN))
	username_input.text_submitted.connect(func(_value): email_input.grab_focus())
	email_input.text_submitted.connect(func(_value): password_input.grab_focus())
	password_input.text_submitted.connect(func(_value): confirm_input.grab_focus())
	confirm_input.text_submitted.connect(func(_value): _on_register_pressed())
	_clear_errors()
	username_input.grab_focus()


## Client-side checks that mirror the backend, keyed like DRF field errors.
func validate_form(username: String, email: String, password: String, confirm: String) -> Dictionary:
	var errors := {}
	if _username_regex.search(username) == null:
		errors["username"] = "3-20 characters: letters, digits, _ and -."
	if not _looks_like_email(email):
		errors["email"] = "Enter a valid email address."
	if password.length() < MIN_PASSWORD_LENGTH:
		errors["password"] = "At least %d characters." % MIN_PASSWORD_LENGTH
	elif password.is_valid_int():
		errors["password"] = "The password cannot be only digits."
	if confirm != password:
		errors["confirm"] = "The passwords do not match."
	return errors


func _on_register_pressed() -> void:
	if _is_submitting:
		return
	var username := username_input.text.strip_edges()
	var email := email_input.text.strip_edges()
	var password := password_input.text
	_clear_errors()
	var errors := validate_form(username, email, password, confirm_input.text)
	if not errors.is_empty():
		_show_errors(errors)
		return

	_set_submitting(true)
	var response: Dictionary = await ApiClient.post_json(
		"users/register/",
		{"username": username, "email": email, "password": password}
	)
	if not response.get("ok", false):
		_set_submitting(false)
		var field_errors := ApiClient.field_errors(response)
		if field_errors.is_empty():
			form_error.text = ApiClient.error_message(response, "Registration failed.")
		else:
			_show_errors(field_errors)
		return

	var data: Dictionary = response.get("data", {})
	var access := str(data.get("access", ""))
	if access.is_empty():
		# Older backends do not log in on sign-up.
		SceneRouter.go_to(SceneRouter.LOGIN)
		return
	SessionStore.begin_session(str(data.get("username", username)), access, str(data.get("refresh", "")))
	SceneRouter.go_to(SceneRouter.CHARACTER_CREATE)


func _looks_like_email(email: String) -> bool:
	var at := email.find("@")
	return at > 0 and email.find(".", at) > at + 1 and not email.ends_with(".") and not email.contains(" ")


## Field name -> [input, error label], in form order.
func _fields() -> Dictionary:
	return {
		"username": [username_input, username_error],
		"email": [email_input, email_error],
		"password": [password_input, password_error],
		"confirm": [confirm_input, confirm_error],
	}


func _show_errors(errors: Dictionary) -> void:
	var fields := _fields()
	var unmatched := PackedStringArray()
	for field in errors:
		if fields.has(field):
			fields[field][1].text = str(errors[field])
		else:
			unmatched.append(str(errors[field]))
	form_error.text = "\n".join(unmatched)
	for field in fields:
		if errors.has(field):
			fields[field][0].grab_focus()
			break


func _clear_errors() -> void:
	for field_nodes in _fields().values():
		field_nodes[1].text = ""
	form_error.text = ""


func _set_submitting(value: bool) -> void:
	_is_submitting = value
	register_button.disabled = value
	back_button.disabled = value
	for field_nodes in _fields().values():
		field_nodes[0].editable = not value
	loading_label.visible = value
