extends Node

## Exercises ApiClient against a tiny in-process HTTP server that mimics the
## backend's JWT endpoints: access "access-2" is valid, refresh "refresh-1"
## rotates to "refresh-2", anything else is rejected with 401.

const PORT := 18765

var _server := FakeHttpServer.new()
var _refresh_calls := 0
var _logout_tokens: Array = []
var _expired_count := 0


func _ready() -> void:
	# The router would replace this test scene with the login screen.
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.session_expired.connect(func(): _expired_count += 1)
	_server.handler = _handle
	add_child(_server)
	if _server.listen(PORT) != OK:
		_fail("FAKE_SERVER_LISTEN_FAILED")
		return
	ApiClient.base_url = _server.base_url(PORT)

	if not _check_helpers() or not await _check_ping():
		return
	if not await _check_concurrent_refresh():
		return
	if not await _check_expired_session():
		return
	if not await _check_logout():
		return
	print("API_CLIENT_OK refresh_calls=%d" % _refresh_calls)
	get_tree().quit(0)


func _check_helpers() -> bool:
	if ApiClient.unwrap_list([1, 2]).size() != 2 or ApiClient.unwrap_list({"results": [1]}).size() != 1 or not ApiClient.unwrap_list(null).is_empty():
		return _fail("UNWRAP_LIST_FAILED")
	if ApiClient.error_message({"error": {"message": "Nope"}}, "x") != "Nope" or ApiClient.error_message({}, "fallback") != "fallback":
		return _fail("ERROR_MESSAGE_FAILED")
	if ApiClient.server_host() != "127.0.0.1:%d" % PORT:
		return _fail("SERVER_HOST_FAILED %s" % ApiClient.server_host())
	return true


func _check_ping() -> bool:
	if not await ApiClient.ping():
		return _fail("PING_FAILED")
	var crash: Dictionary = await ApiClient.get_json("crash/")
	if crash.status != 500 or crash.error.code != "SERVER_ERROR" or not crash.error.message.contains("HTTP 500"):
		return _fail("SERVER_ERROR_PAGE_FAILED %s" % crash)
	return true


func _check_concurrent_refresh() -> bool:
	ApiClient.set_tokens("access-1", "refresh-1")
	var results: Array = []
	_fetch_into(results)
	_fetch_into(results)
	if not await _wait_until(func(): return results.size() == 2):
		return _fail("CONCURRENT_REQUESTS_TIMED_OUT")
	for response in results:
		if not response.get("ok", false):
			return _fail("RETRY_AFTER_REFRESH_FAILED %s" % response)
	if _refresh_calls != 1:
		return _fail("REFRESH_NOT_SINGLE_FLIGHT calls=%d" % _refresh_calls)
	if ApiClient.access_token != "access-2" or ApiClient.refresh_token != "refresh-2":
		return _fail("ROTATED_TOKENS_NOT_STORED")
	if _expired_count != 0:
		return _fail("SESSION_EXPIRED_TOO_EARLY")
	return true


func _check_expired_session() -> bool:
	ApiClient.set_tokens("access-1", "revoked")
	var response: Dictionary = await ApiClient.get_json("characters/my/")
	if int(response.get("status", 0)) != 401:
		return _fail("EXPIRED_STATUS_FAILED %s" % response)
	if _expired_count != 1 or ApiClient.has_tokens():
		return _fail("SESSION_EXPIRED_NOT_EMITTED count=%d" % _expired_count)
	# Requests without a token (e.g. a wrong password at login) must not expire anything.
	await ApiClient.get_json("characters/my/")
	if _expired_count != 1:
		return _fail("ANONYMOUS_401_EXPIRED_SESSION")
	return true


func _check_logout() -> bool:
	ApiClient.set_tokens("access-2", "refresh-2")
	await ApiClient.logout()
	if _logout_tokens != ["refresh-2"] or ApiClient.has_tokens():
		return _fail("LOGOUT_FAILED %s" % [_logout_tokens])
	return true


func _fetch_into(results: Array) -> void:
	results.append(await ApiClient.get_json("characters/my/"))


func _wait_until(condition: Callable, timeout_seconds: float = 10.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(timeout_seconds * 1000)
	while not condition.call():
		if Time.get_ticks_msec() > deadline:
			return false
		await get_tree().process_frame
	return true


func _fail(code: String) -> bool:
	printerr(code)
	get_tree().quit(1)
	return false


func _handle(path: String, head: String, payload: Variant) -> Array:
	if path == "/api/users/token/refresh/":
		_refresh_calls += 1
		if payload is Dictionary and payload.get("refresh") == "refresh-1":
			return [200, {"access": "access-2", "refresh": "refresh-2"}]
	elif path == "/api/users/logout/":
		_logout_tokens.append(payload.get("refresh") if payload is Dictionary else null)
		return [200, {}]
	elif path == "/api/crash/":
		return [500, null, "<html><body><h1>Server Error (500)</h1></body></html>"]
	elif path == "/api/classes/":
		return [200, {"count": 0, "results": []}]
	elif head.contains("Authorization: Bearer access-2"):
		return [200, {"name": "Tester"}]
	return [401, {"detail": "Token is invalid or expired"}]
