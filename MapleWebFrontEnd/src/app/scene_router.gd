extends Node

## Scene paths and navigation. Sends the player back to the login screen when
## ApiClient reports that the session can no longer be refreshed.
##
## Character, Inventory, Enhancement and Shop are pages of the hub: going to
## one while the hub is open switches the hub's page; from anywhere else it
## opens the hub on that page.

const LOGIN := "res://src/features/auth/presentation/login_screen.tscn"
const REGISTER := "res://src/features/auth/presentation/register_screen.tscn"
const CHARACTER_CREATE := "res://src/features/character/presentation/character_create_screen.tscn"
const HUB := "res://src/features/hub/presentation/hub_screen.tscn"
const BATTLE := "res://src/features/battle/presentation/battle_screen.tscn"
const CHARACTER := "res://src/features/character/presentation/character_profile.tscn"
const INVENTORY := "res://src/features/inventory/presentation/inventory_screen.tscn"
const ENHANCEMENT := "res://src/features/enhancement/presentation/enhancement_screen.tscn"
const SHOP := "res://src/features/shop/presentation/shop_screen.tscn"

## Hub page id -> the screen it embeds.
const HUB_SCENES := {
	"character": CHARACTER,
	"inventory": INVENTORY,
	"enhance": ENHANCEMENT,
	"shop": SHOP,
}

## What the next scene should open with (e.g. {"tab": "aurora"}); read once
## with take_args().
var _args: Dictionary = {}


func _ready() -> void:
	ApiClient.session_expired.connect(go_to_login)


## Deferred so it is safe to call from a scene's _ready, while the tree is still
## adding that scene.
func go_to(scene_path: String, args: Dictionary = {}) -> void:
	var page := hub_page_for(scene_path)
	if not page.is_empty():
		var hub := _open_hub()
		if hub != null:
			hub.open_page.call_deferred(page, args)
			return
		_args = {"page": page, "page_args": args}
		get_tree().change_scene_to_file.call_deferred(HUB)
		return
	_args = args
	get_tree().change_scene_to_file.call_deferred(scene_path)


## The hub page that shows `scene_path` ("home" for the hub itself), or "".
static func hub_page_for(scene_path: String) -> String:
	if scene_path == HUB:
		return "home"
	for page in HUB_SCENES:
		if HUB_SCENES[page] == scene_path:
			return page
	return ""


## The arguments passed to go_to for the current scene, cleared after reading.
func take_args() -> Dictionary:
	var args := _args
	_args = {}
	return args


## Sets the arguments the next screen will take (used by the hub when it
## creates a page).
func hand_args(args: Dictionary) -> void:
	_args = args


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


func _open_hub() -> Node:
	var scene := get_tree().current_scene
	return scene if scene != null and scene.has_method("open_page") else null
