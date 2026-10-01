extends Node

var username: String = ""
var access_token: String = ""
var refresh_token: String = ""
var character: Dictionary = {}
var active_battle_id: String = ""


func begin_session(login_name: String, access: String, refresh: String) -> void:
	username = login_name
	access_token = access
	refresh_token = refresh
	ApiClient.set_access_token(access_token)


func clear_session() -> void:
	username = ""
	access_token = ""
	refresh_token = ""
	character = {}
	active_battle_id = ""
	ApiClient.clear_access_token()


func has_session() -> bool:
	return not access_token.is_empty()

