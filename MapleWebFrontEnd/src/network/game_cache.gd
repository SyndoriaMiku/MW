extends Node

## Read-through cache in front of ApiClient GETs (autoload "GameCache"), so
## screens and hub pages share one copy of the data instead of each asking the
## server again.
##
## - Reference data (classes, jobs, equipment slots, dungeons, shop categories,
##   skills) rarely changes: kept in memory for REFERENCE_TTL and, against the
##   deployed (https) server, on disk so the next launch starts without asking.
## - Player data (character, profile, inventory, equipment, buy back, shop
##   stock, active battle, Lumen preview) is kept in memory for PLAYER_TTL and
##   dropped as soon as any POST may have changed it (ApiClient.posted).
## - Identical requests in flight at the same time share one request.
##
## Reads return copies, so callers may sort or edit what they get.

signal invalidated(paths: Array)

const REFERENCE_TTL := 6 * 3600.0
const PLAYER_TTL := 300.0
## Reference data that Studio edits often, so changes show up sooner.
const SHORT_TTL := {
	"world/normal-dungeons/": 1800.0,
	"world/boss-dungeons/": 1800.0,
	"world/regions/": 1800.0,
}
const DISK_DIR := "user://cache/"

## Path prefix -> kind. The longest matching prefix wins; other paths are not
## cached.
const RULES := {
	"classes/": "reference",
	"skills/": "reference",
	"inventory/slots/": "reference",
	"world/normal-dungeons/": "reference",
	"world/boss-dungeons/": "reference",
	"world/regions/": "reference",
	"shops/categories/": "reference",
	"items/templates/": "reference",
	"skills/learnable/": "player",
	"quests/": "player",
	"party/party/my/": "player",
	"characters/my/": "player",
	"users/profile/": "player",
	"inventory/": "player",
	"battles/active/": "player",
	"shops/items/": "player",
	"items/lumen/preview/": "player",
}

## POST path prefix -> the cached paths (prefixes) it may change.
const INVALIDATES := {
	"inventory/": ["inventory/", "characters/my/", "users/profile/", "items/lumen/preview/", "quests/"],
	"shops/": ["inventory/", "users/profile/", "shops/items/", "characters/my/", "quests/"],
	"items/": ["inventory/", "characters/my/", "users/profile/", "items/lumen/preview/", "quests/"],
	"world/": ["battles/active/", "characters/my/", "party/"],
	"battles/": ["battles/active/", "characters/my/", "users/profile/", "inventory/", "quests/", "skills/learnable/", "party/"],
	"characters/": ["characters/my/", "inventory/", "skills/learnable/", "quests/"],
	"quests/": ["quests/", "characters/my/", "users/profile/", "inventory/", "skills/learnable/"],
	"party/": ["battles/active/", "party/"],
	"market/": ["inventory/", "users/profile/"],
}

## Cache key ("GET path" or "ALL path") -> {"data", "saved_at"}.
var _entries: Dictionary = {}
## Cache key -> InFlight, for requests still waiting on the server.
var _in_flight: Dictionary = {}
var _disk_loaded_for := ""
## Requests that reached the server, for tests and diagnostics.
var server_requests := 0


func _ready() -> void:
	ApiClient.posted.connect(_on_posted)


## Like ApiClient.get_json, served from the cache when fresh. `force` skips the
## cache (Refresh buttons).
func get_json(path: String, force: bool = false) -> Dictionary:
	return await _fetch("GET", path, force)


## Like ApiClient.get_all (every page of a list), served from the cache.
func get_all(path: String, force: bool = false) -> Dictionary:
	return await _fetch("ALL", path, force)


## Stores a response the caller already has (e.g. parts of session/bootstrap/).
func store(path: String, data: Variant, all_pages: bool = false) -> void:
	if _kind(path).is_empty():
		return
	_put(("ALL " if all_pages else "GET ") + path, data)


## Forgets cached paths starting with any of `prefixes`.
func invalidate(prefixes: Array) -> void:
	var dropped := []
	for key in _entries.keys():
		var path := str(key).substr(4)
		if _kind(path) != "player":
			continue
		for prefix in prefixes:
			if path.begins_with(prefix):
				_entries.erase(key)
				dropped.append(path)
				break
	if not dropped.is_empty():
		invalidated.emit(dropped)


## Forgets the player's data (sign in, sign out, Refresh).
func clear_player() -> void:
	for key in _entries.keys():
		if _kind(str(key).substr(4)) == "player":
			_entries.erase(key)
	invalidated.emit(["*"])


## Forgets everything, reference data on disk included (Refresh buttons).
func clear_all() -> void:
	_entries.clear()
	_disk_loaded_for = _disk_key()
	if _uses_disk():
		DirAccess.remove_absolute(_disk_path())
	invalidated.emit(["*"])


func is_cached(path: String, all_pages: bool = false) -> bool:
	var key := ("ALL " if all_pages else "GET ") + path
	return _entries.has(key) and _is_fresh(path, _entries[key])


func _fetch(mode: String, path: String, force: bool) -> Dictionary:
	var kind := _kind(path)
	if kind.is_empty():
		return await _request(mode, path)
	_load_disk()
	var key := "%s %s" % [mode, path]
	if not force and _entries.has(key) and _is_fresh(path, _entries[key]):
		return {"ok": true, "status": 200, "data": _copy(_entries[key].data), "cached": true}
	if _in_flight.has(key):
		var shared: Dictionary = await _in_flight[key].finished
		return _copy_response(shared)
	var flight := InFlight.new()
	_in_flight[key] = flight
	var response := await _request(mode, path)
	_in_flight.erase(key)
	if response.get("ok", false):
		_put(key, response.get("data"))
	flight.finished.emit(response)
	return _copy_response(response)


func _request(mode: String, path: String) -> Dictionary:
	server_requests += 1
	if mode == "ALL":
		return await ApiClient.get_all(path)
	return await ApiClient.get_json(path)


func _put(key: String, data: Variant) -> void:
	_entries[key] = {"data": _copy(data), "saved_at": Time.get_unix_time_from_system()}
	if _kind(key.substr(4)) == "reference":
		_save_disk()


func _is_fresh(path: String, entry: Dictionary) -> bool:
	var ttl := REFERENCE_TTL if _kind(path) == "reference" else PLAYER_TTL
	for prefix in SHORT_TTL:
		if path.begins_with(prefix):
			ttl = SHORT_TTL[prefix]
	return Time.get_unix_time_from_system() - float(entry.get("saved_at", 0.0)) < ttl


func _kind(path: String) -> String:
	var best := ""
	for prefix in RULES:
		if path.begins_with(prefix) and prefix.length() > best.length():
			best = prefix
	return RULES.get(best, "")


func _on_posted(path: String, _response: Dictionary) -> void:
	var prefixes := []
	for prefix in INVALIDATES:
		if path.begins_with(prefix):
			prefixes.append_array(INVALIDATES[prefix])
	if path.begins_with("users/"):
		clear_player()
	elif not prefixes.is_empty():
		invalidate(prefixes)


## Reference data is only kept on disk for the deployed server: a local
## development backend changes too often for that.
func _uses_disk() -> bool:
	return ApiClient.base_url.begins_with("https://")


func _disk_key() -> String:
	return ApiClient.base_url.md5_text()


func _disk_path() -> String:
	return DISK_DIR + "reference_%s.json" % _disk_key()


func _load_disk() -> void:
	if _disk_loaded_for == _disk_key():
		return
	_disk_loaded_for = _disk_key()
	if not _uses_disk() or not FileAccess.file_exists(_disk_path()):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(_disk_path()))
	if not parsed is Dictionary:
		return
	for key in parsed:
		var entry: Variant = parsed[key]
		if entry is Dictionary and not _entries.has(key) and _is_fresh(str(key).substr(4), entry):
			_entries[key] = entry


func _save_disk() -> void:
	if not _uses_disk():
		return
	var reference := {}
	for key in _entries:
		if _kind(str(key).substr(4)) == "reference":
			reference[key] = _entries[key]
	DirAccess.make_dir_recursive_absolute(DISK_DIR)
	var file := FileAccess.open(_disk_path(), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(reference))


static func _copy(value: Variant) -> Variant:
	return value.duplicate(true) if value is Dictionary or value is Array else value


static func _copy_response(response: Dictionary) -> Dictionary:
	return response.duplicate(true)


## Lets callers that asked for a path already in flight wait for its answer.
class InFlight:
	extends RefCounted
	signal finished(response: Dictionary)
