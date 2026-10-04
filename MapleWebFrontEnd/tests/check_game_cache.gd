extends Node

## GameCache: repeated and concurrent reads reach the server once, POSTs drop
## the player data they may change (and only that), reads are copies, and
## signing in again forgets the previous player's data.

const PORT := 18773

var _server := FakeHttpServer.new()
var _hits: Dictionary = {}


func _ready() -> void:
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		_fail("FAKE_SERVER_LISTEN_FAILED")
		return
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.base_url = _server.base_url(PORT)
	SessionStore.begin_session("cache_tester", "token", "")
	if not await _check():
		return
	print("GAME_CACHE_OK hits=%s" % [_hits])
	get_tree().quit(0)


func _check() -> bool:
	var first: Dictionary = await GameCache.get_json("users/profile/")
	var second: Dictionary = await GameCache.get_json("users/profile/")
	if not first.ok or not second.get("cached", false) or _hits.get("/api/users/profile/", 0) != 1:
		return _fail("REPEAT_READ_FAILED %s" % [_hits])

	# Two pages asking at once share one request.
	var results := []
	var ask := func(): results.append(await GameCache.get_all("inventory/"))
	ask.call()
	ask.call()
	while results.size() < 2:
		await get_tree().process_frame
	if _hits.get("/api/inventory/", 0) != 1 or results[0].data.size() != 2 or results[1].data.size() != 2:
		return _fail("SHARED_FLIGHT_FAILED %s" % [_hits])

	# Reads are copies.
	results[0].data.clear()
	var again: Dictionary = await GameCache.get_all("inventory/")
	if again.data.size() != 2:
		return _fail("COPY_FAILED")

	await GameCache.get_all("classes/")
	await GameCache.get_all("inventory/slots/")
	# Equipping drops the inventory, character and profile, not reference data.
	await ApiClient.post_json("inventory/5/equip/", {"slot_index": 0})
	if GameCache.is_cached("inventory/", true) or GameCache.is_cached("users/profile/"):
		return _fail("POST_INVALIDATION_FAILED")
	if not GameCache.is_cached("classes/", true) or not GameCache.is_cached("inventory/slots/", true):
		return _fail("REFERENCE_DROPPED_BY_POST")
	await GameCache.get_all("inventory/")
	if _hits.get("/api/inventory/", 0) != 2:
		return _fail("REFETCH_AFTER_POST_FAILED %s" % [_hits])

	# A failed request is not cached.
	await GameCache.get_json("characters/my/")
	await GameCache.get_json("characters/my/")
	if _hits.get("/api/characters/my/", 0) != 2:
		return _fail("ERROR_CACHED %s" % [_hits])

	# Uncached paths always reach the server.
	await GameCache.get_json("battles/abc/")
	await GameCache.get_json("battles/abc/")
	if _hits.get("/api/battles/abc/", 0) != 2:
		return _fail("UNCACHED_PATH_CACHED")

	# A new sign-in forgets the player data but keeps reference data.
	GameCache.store("users/profile/", {"lumis": 1})
	SessionStore.begin_session("someone_else", "token", "")
	if GameCache.is_cached("users/profile/") or not GameCache.is_cached("classes/", true):
		return _fail("SIGN_IN_CLEAR_FAILED")
	GameCache.clear_all()
	if GameCache.is_cached("classes/", true):
		return _fail("CLEAR_ALL_FAILED")
	return true


func _handle(path: String, head: String, _payload: Variant) -> Array:
	_hits[path] = int(_hits.get(path, 0)) + 1
	if head.begins_with("POST"):
		return [200, {"status": "Done."}]
	match path:
		"/api/users/profile/":
			return [200, {"username": "cache_tester", "lumis": 10}]
		"/api/inventory/":
			return [200, {"count": 2, "next": null, "results": [{"id": 5}, {"id": 6}]}]
		"/api/classes/", "/api/inventory/slots/":
			return [200, {"count": 0, "next": null, "results": []}]
		"/api/battles/abc/":
			return [200, {"id": "abc"}]
	return [404, {"detail": "Not found."}]


func _fail(code: String) -> bool:
	printerr(code)
	get_tree().quit(1)
	return false
