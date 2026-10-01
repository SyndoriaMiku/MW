extends Node

## Scene paths and navigation. Sends the player back to the login screen when
## ApiClient reports that the session can no longer be refreshed.

const LOGIN := "res://src/features/auth/presentation/login_screen.tscn"
const LAUNCHER := "res://src/features/world/presentation/battle_launcher.tscn"
const BATTLE := "res://src/features/battle/presentation/battle_demo.tscn"
const CHARACTER := "res://src/features/character/presentation/character_profile.tscn"
const INVENTORY := "res://src/features/inventory/presentation/inventory_screen.tscn"
const ENHANCEMENT := "res://src/features/enhancement/presentation/enhancement_screen.tscn"


func _ready() -> void:
	ApiClient.session_expired.connect(go_to_login)


## Deferred so it is safe to call from a scene's _ready, while the tree is still
## adding that scene.
func go_to(scene_path: String) -> void:
	get_tree().change_scene_to_file.call_deferred(scene_path)


func go_to_login() -> void:
	SessionStore.clear_session()
	go_to(LOGIN)


## For screens that need a signed-in player: redirects to login when there is no
## session and returns false so the caller can stop.
func require_session() -> bool:
	if SessionStore.has_session():
		return true
	go_to_login()
	return false
