extends Node

## Exercises ApiClient against a tiny in-process HTTP server that mimics the
## backend's JWT endpoints: access "access-2" is valid, refresh "refresh-1"
## rotates to "refresh-2", anything else is rejected with 401.

const PORT := 18765

var _server := TCPServer.new()
var _peers: Array = []
var _refresh_calls := 0
var _logout_tokens: Array = []
var _expired_count := 0


func _ready() -> void:
	# The router would replace this test scene with the login screen.
	ApiClient.session_expired.disconnect(SceneRouter.go_to_login)
	ApiClient.session_expired.connect(func(): _expired_count += 1)
	if _server.listen(PORT, "127.0.0.1") != OK:
		_fail("FAKE_SERVER_LISTEN_FAILED")
		return
	ApiClient.base_url = "http://127.0.0.1:%d/api/" % PORT

	if not _check_helpers():
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


func _process(_delta: float) -> void:
	while _server.is_connection_available():
		_peers.append({"peer": _server.take_connection(), "data": PackedByteArray()})
	for entry in _peers.duplicate():
		var peer: StreamPeerTCP = entry.peer
		peer.poll()
		var available := peer.get_available_bytes()
		if available > 0:
			var chunk: Array = peer.get_data(available)
			var data: PackedByteArray = entry.data
			data.append_array(chunk[1])
			entry.data = data
		var text: String = entry.data.get_string_from_utf8()
		var header_end := text.find("\r\n\r\n")
		if header_end < 0:
			continue
		var head := text.substr(0, header_end)
		var content_length := 0
		for line in head.split("\r\n"):
			if line.to_lower().begins_with("content-length:"):
				content_length = int(line.get_slice(":", 1).strip_edges())
		var body := text.substr(header_end + 4)
		if body.to_utf8_buffer().size() < content_length:
			continue
		_peers.erase(entry)
		_respond(peer, head, body)


func _respond(peer: StreamPeerTCP, head: String, body: String) -> void:
	var path := head.get_slice("\r\n", 0).get_slice(" ", 1)
	var payload: Variant = JSON.parse_string(body) if not body.is_empty() else {}
	var status := 401
	var reply: Dictionary = {"detail": "Token is invalid or expired"}
	if path == "/api/users/token/refresh/":
		_refresh_calls += 1
		if payload is Dictionary and payload.get("refresh") == "refresh-1":
			status = 200
			reply = {"access": "access-2", "refresh": "refresh-2"}
	elif path == "/api/users/logout/":
		_logout_tokens.append(payload.get("refresh") if payload is Dictionary else null)
		status = 200
		reply = {}
	elif head.contains("Authorization: Bearer access-2"):
		status = 200
		reply = {"name": "Tester"}
	var json := JSON.stringify(reply)
	var response := "HTTP/1.1 %d X\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % [
		status, json.to_utf8_buffer().size(), json,
	]
	peer.put_data(response.to_utf8_buffer())
	peer.disconnect_from_host()
