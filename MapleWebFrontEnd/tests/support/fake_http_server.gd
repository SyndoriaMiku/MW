class_name FakeHttpServer
extends Node

## Minimal HTTP/1.1 server for tests. `handler` receives (path, head, payload)
## and returns [status_code, reply_dictionary].

var handler: Callable = func(_path: String, _head: String, _payload: Variant) -> Array:
	return [503, {"detail": "Fake server has no handler."}]

var _server := TCPServer.new()
var _peers: Array = []


func listen(port: int) -> Error:
	return _server.listen(port, "127.0.0.1")


func base_url(port: int) -> String:
	return "http://127.0.0.1:%d/api/" % port


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
		var path := head.get_slice("\r\n", 0).get_slice(" ", 1)
		var payload: Variant = JSON.parse_string(body) if not body.is_empty() else {}
		var result: Array = handler.call(path, head, payload)
		_reply(peer, int(result[0]), result[1])


func _reply(peer: StreamPeerTCP, status: int, reply: Variant) -> void:
	var json := JSON.stringify(reply)
	var response := "HTTP/1.1 %d X\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % [
		status, json.to_utf8_buffer().size(), json,
	]
	peer.put_data(response.to_utf8_buffer())
	peer.disconnect_from_host()
