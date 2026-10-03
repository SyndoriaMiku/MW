extends Node

## Scene paths and navigation. Sends the player back to the login screen when
## ApiClient reports that the session can no longer be refreshed.

const LOGIN := "res://src/features/auth/presentation/login_screen.tscn"
const REGISTER := "res://src/features/auth/presentation/register_screen.tscn"
const CHARACTER_CREATE := "res://src/features/character/presentation/character_create_screen.tscn"
const LAUNCHER := "res://src/features/world/presentation/battle_launcher.tscn"
const BATTLE := "res://src/features/battle/presentation/battle_screen.tscn"
const CHARACTER := "res://src/features/character/presentation/character_profile.tscn"
const INVENTORY := "res://src/features/inventory/presentation/inventory_screen.tscn"
const ENHANCEMENT := "res://src/features/enhancement/presentation/enhancement_screen.tscn"
const SHOP := "res://src/features/shop/presentation/shop_screen.tscn"


func _ready() -> void:
	ApiClient.session_expired.connect(go_to_login)


## What the next scene should open with (e.g. {"tab": "aurora"}); read once
## with take_args().
var _args: Dictionary = {}


## Deferred so it is safe to call from a scene's _ready, while the tree is still
## adding that scene.
func go_to(scene_path: String, args: Dictionary = {}) -> void:
	_args = args
	get_tree().change_scene_to_file.call_deferred(scene_path)


## The arguments passed to go_to for the current scene, cleared after reading.
func take_args() -> Dictionary:
	var args := _args
	_args = {}
	return args


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
