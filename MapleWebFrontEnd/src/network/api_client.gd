extends Node

## JSON HTTP client for the Django backend. Owns the JWT pair: an authenticated
## request that gets 401 refreshes the access token once and is retried, and
## session_expired is emitted when the session cannot be recovered.

signal session_expired
signal _refresh_finished(success: bool)

const DEFAULT_BASE_URL := "http://127.0.0.1:8000/api"
const BASE_URL_SETTING := "maple_world/network/api_base_url"
const BASE_URL_ARG := "--api-url="
const REQUEST_TIMEOUT_SECONDS := 15.0
const REFRESH_PATH := "users/token/refresh/"
const LOGOUT_PATH := "users/logout/"

var base_url: String = DEFAULT_BASE_URL
var access_token: String = ""
var refresh_token: String = ""

var _is_refreshing := false


func _init() -> void:
	base_url = _configured_base_url()


## Command line (`godot -- --api-url=...`) wins over the project setting.
static func _configured_base_url() -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with(BASE_URL_ARG):
			return arg.trim_prefix(BASE_URL_ARG)
	return str(ProjectSettings.get_setting(BASE_URL_SETTING, DEFAULT_BASE_URL))


## Host and port of the backend, for display.
func server_host() -> String:
	return base_url.get_slice("://", 1).get_slice("/", 0)


func set_tokens(access: String, refresh: String) -> void:
	access_token = access
	refresh_token = refresh


func clear_tokens() -> void:
	access_token = ""
	refresh_token = ""


func has_tokens() -> bool:
	return not access_token.is_empty()


## Blacklists the refresh token on the server (best effort) and forgets both tokens.
func logout() -> void:
	var token := refresh_token
	clear_tokens()
	if not token.is_empty():
		await _send(LOGOUT_PATH, HTTPClient.METHOD_POST, {"refresh": token}, "")


func get_json(path: String) -> Dictionary:
	return await _request_json(path, HTTPClient.METHOD_GET)


func post_json(path: String, payload: Dictionary = {}) -> Dictionary:
	return await _request_json(path, HTTPClient.METHOD_POST, payload)


## DRF list endpoints return either a plain array or a paginated {"results": [...]}.
static func unwrap_list(payload: Variant) -> Array:
	if payload is Array:
		return payload
	if payload is Dictionary:
		var results: Variant = payload.get("results", [])
		return results if results is Array else []
	return []


## JSON numbers arrive as floats, so an ID of 5 would print as "5.0". IDs used in
## URLs or as lookup keys must go through this to read "5".
static func id_string(value: Variant) -> String:
	if value == null:
		return ""
	if value is float and is_equal_approx(value, roundf(value)):
		return str(int(value))
	return str(value)


static func error_message(response: Dictionary, fallback: String) -> String:
	var error: Variant = response.get("error", {})
	if error is Dictionary:
		return str(error.get("message", fallback))
	return fallback


func _request_json(path: String, method: int, payload: Dictionary = {}) -> Dictionary:
	var sent_token := access_token
	var response := await _send(path, method, payload, sent_token)
	if int(response.get("status", 0)) != 401 or sent_token.is_empty():
		return response

	# Another request may have rotated the token while this one was in flight.
	if access_token == sent_token:
		if not await _refresh_access_token():
			_expire_session()
			return response
	elif access_token.is_empty():
		return response

	response = await _send(path, method, payload, access_token)
	if int(response.get("status", 0)) == 401:
		_expire_session()
	return response


## Only one refresh runs at a time: the backend rotates and blacklists refresh
## tokens, so a second concurrent refresh with the old token would fail.
func _refresh_access_token() -> bool:
	if _is_refreshing:
		return await _refresh_finished
	if refresh_token.is_empty():
		return false

	_is_refreshing = true
	var response := await _send(REFRESH_PATH, HTTPClient.METHOD_POST, {"refresh": refresh_token}, "")
	var data: Variant = response.get("data", {})
	var success: bool = (
		response.get("ok", false)
		and data is Dictionary
		and not str(data.get("access", "")).is_empty()
		and not refresh_token.is_empty()
	)
	if success:
		access_token = str(data.get("access"))
		refresh_token = str(data.get("refresh", refresh_token))
	_is_refreshing = false
	_refresh_finished.emit(success)
	return success


func _expire_session() -> void:
	if access_token.is_empty() and refresh_token.is_empty():
		return
	clear_tokens()
	session_expired.emit()


func _send(path: String, method: int, payload: Dictionary, token: String) -> Dictionary:
	var request := HTTPRequest.new()
	request.timeout = REQUEST_TIMEOUT_SECONDS
	add_child(request)

	var headers := PackedStringArray(["Accept: application/json"])
	if method != HTTPClient.METHOD_GET:
		headers.append("Content-Type: application/json")
	if not token.is_empty():
		headers.append("Authorization: Bearer %s" % token)

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
	if transport_result == HTTPRequest.RESULT_TIMEOUT:
		return {
			"ok": false,
			"status": 0,
			"error": {"code": "NETWORK_TIMEOUT", "message": "The server took too long to respond."},
		}
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


## Field errors from a DRF validation response ({"name": ["Taken."], ...}),
## keyed by field, or empty when the request did not fail validation.
static func field_errors(response: Dictionary) -> Dictionary:
	var error: Variant = response.get("error", {})
	if error is Dictionary and error.get("fields") is Dictionary:
		return error.fields
	return {}


## Reads the backend's error envelope ({"code", "message", "fields"}, see
## MapleWebBackEnd/apps/api_errors.py) and the older bare shapes it wraps.
func _normalize_error(payload: Variant) -> Dictionary:
	if not payload is Dictionary:
		return {"code": "API_ERROR", "message": "The server rejected the request."}
	if payload.get("error") is Dictionary:
		return payload.error

	var message := ""
	for key in ["message", "detail", "error"]:
		if payload.get(key) is String:
			message = payload[key]
			break
	var fields := _join_field_messages(payload.get("fields")) if payload.get("fields") is Dictionary else {}
	if fields.is_empty() and message.is_empty():
		fields = _join_field_messages(payload)
	if message.is_empty():
		message = str(fields.values()[0]) if not fields.is_empty() else "The server rejected the request."

	var error := {"code": str(payload.get("code", "API_ERROR")), "message": message}
	if not fields.is_empty():
		error["fields"] = fields
	return error


## {"name": ["Taken.", "Too long."]} -> {"name": "Taken. Too long."}
static func _join_field_messages(raw_fields: Dictionary) -> Dictionary:
	var fields := {}
	for key in raw_fields:
		if key == "code":
			continue
		var messages := PackedStringArray()
		var value: Variant = raw_fields[key]
		for message in (value if value is Array else [value]):
			messages.append(str(message))
		fields[str(key)] = " ".join(messages)
	return fields
