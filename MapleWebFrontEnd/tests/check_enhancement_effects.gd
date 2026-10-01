extends Node


func _ready() -> void:
	SessionStore.begin_session("effect-test", "offline-token", "")
	ApiClient.base_url = "http://127.0.0.1:1/api"
	var packed: PackedScene = load("res://src/features/enhancement/presentation/enhancement_screen.tscn")
	var screen: Control = packed.instantiate()
	add_child(screen)
	await get_tree().process_frame
	await screen._play_lumen_result("success", "Upgrade successful!")
	if screen.result_effect_layer.visible:
		printerr("ENHANCEMENT_SUCCESS_EFFECT_DID_NOT_FINISH")
		get_tree().quit(1)
		return
	await screen._play_lumen_result("failure", "Level remains unchanged.")
	await screen._play_lumen_result("heavy_failure", "Item became a fragment.")
	if screen.result_effect_layer.visible:
		printerr("ENHANCEMENT_FAILURE_EFFECT_DID_NOT_FINISH")
		get_tree().quit(1)
		return
	print("ENHANCEMENT_RESULT_EFFECTS_OK")
	get_tree().quit(0)
