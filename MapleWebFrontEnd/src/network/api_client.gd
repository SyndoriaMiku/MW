extends Node

## Minimal JSON HTTP client. Authentication refresh and retry policy will be
## added when the backend contract is finalized.

var base_url: String = "http://127.0.0.1:8000/api"
var access_token: String = ""


func set_access_token(token: String) -> void:
	access_token = token


func clear_access_token() -> void:
	access_token = ""


func get_json(path: String) -> Dictionary:
	return await _request_json(path, HTTPClient.METHOD_GET)


func post_json(path: String, payload: Dictionary = {}) -> Dictionary:
	return await _request_json(path, HTTPClient.METHOD_POST, payload)


func _request_json(path: String, method: int, payload: Dictionary = {}) -> Dictionary:
	var request := HTTPRequest.new()
	add_child(request)

	var headers := PackedStringArray(["Accept: application/json"])
	if method != HTTPClient.METHOD_GET:
		headers.append("Content-Type: application/json")
	if not access_token.is_empty():
		headers.append("Authorization: Bearer %s" % access_token)

	var body := "" if payload.is_empty() else JSON.stringify(payload)
	var url := "%s/%s" % [base_url.trim_suffix("/"), path.trim_prefix("/")]
	var start_error := request.request(url, headers, method, body)
	if start_error != OK:
		request.queue_free()
		return {
			"ok": false,
			"status": 0,
			"error": {"code": "NETWORK_START_FAILED", "message": error_string(start_error)},
		}

	var result: Array = await request.request_completed
	request.queue_free()

	var transport_result: int = result[0]
	var status_code: int = result[1]
	var response_body: PackedByteArray = result[3]
	if transport_result != HTTPRequest.RESULT_SUCCESS:
		return {
			"ok": false,
			"status": status_code,
			"error": {"code": "NETWORK_REQUEST_FAILED", "message": "Unable to reach the server."},
		}

	var text := response_body.get_string_from_utf8()
	var parsed: Variant = {} if text.is_empty() else JSON.parse_string(text)
	if parsed == null:
		return {
			"ok": false,
			"status": status_code,
			"error": {"code": "INVALID_JSON", "message": "Server returned invalid JSON."},
		}

	if status_code >= 200 and status_code < 300:
		return {"ok": true, "status": status_code, "data": parsed}

	return {
		"ok": false,
		"status": status_code,
		"error": _normalize_error(parsed),
	}


func _normalize_error(payload: Variant) -> Dictionary:
	if payload is Dictionary:
		if payload.has("error") and payload.error is Dictionary:
			return payload.error
		for key in ["detail", "message", "error"]:
			if payload.has(key) and payload[key] is String:
				return {"code": "API_ERROR", "message": payload[key]}
	return {"code": "API_ERROR", "message": "The server rejected the request."}
