extends Node

## Signed-in player state shared between screens. The JWT pair lives in ApiClient.

var username: String = ""
var character: Dictionary = {}
var active_battle_id: String = ""


func begin_session(login_name: String, access: String, refresh: String) -> void:
	username = login_name
	GameCache.clear_player()
	ApiClient.set_tokens(access, refresh)


## Forgets the session locally without contacting the server.
func clear_session() -> void:
	username = ""
	character = {}
	active_battle_id = ""
	GameCache.clear_player()
	ApiClient.clear_tokens()


func logout() -> void:
	await ApiClient.logout()
	clear_session()


func has_session() -> bool:
	return ApiClient.has_tokens()
