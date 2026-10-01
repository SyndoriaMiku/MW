extends Node


func _ready() -> void:
	var packed: PackedScene = load("res://src/features/enhancement/presentation/enhancement_screen.tscn")
	if packed == null:
		printerr("ENHANCEMENT_SCENE_LOAD_FAILED")
		get_tree().quit(1)
		return
	var screen: Control = packed.instantiate()
	var expected_nodes := [
		"%LumenMenuButton", "%AuroraMenuButton", "%SystemPages", "%TargetIcon",
		"%LumenButton", "%LumenRates", "%LumenCost", "%LumenEventInfo",
		"%EssenceSelect", "%RerollButton", "%PendingPanel", "%ResultEffectLayer",
		"%ResultCard", "%ResultTitle", "%ResultSubtitle",
	]
	for node_path in expected_nodes:
		if screen.get_node_or_null(node_path) == null:
			printerr("ENHANCEMENT_NODE_MISSING %s" % node_path)
			screen.free()
			get_tree().quit(1)
			return
	var aurora_text: String = screen._format_aurora_lines([
		{"stat_type": "att", "line_type": "percent", "value": 3},
	])
	if aurora_text.find("ATT") < 0 or aurora_text.find("3%") < 0:
		printerr("ENHANCEMENT_AURORA_FORMAT_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	var icon: Texture2D = ItemIcons.for_template({"name": "Copper Hammer"})
	if icon == null:
		printerr("ENHANCEMENT_ICON_RESOLVE_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	if screen._format_percent(65.0) != "65" or screen._format_percent(12.5) != "12.5":
		printerr("ENHANCEMENT_RATE_FORMAT_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	if screen._format_integer(1234567) != "1,234,567":
		printerr("ENHANCEMENT_COST_FORMAT_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	if screen._lumen_result_visual("success").get("title") != "LUMEN ASCEND SUCCESS":
		printerr("ENHANCEMENT_SUCCESS_EFFECT_MAPPING_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	if screen._lumen_result_visual("heavy_failure").get("title") != "HEAVY FAILURE":
		printerr("ENHANCEMENT_HEAVY_EFFECT_MAPPING_FAILED")
		screen.free()
		get_tree().quit(1)
		return
	print("ENHANCEMENT_UI_OK aurora=%s icon=%s" % [aurora_text, icon.get_class()])
	screen.free()
	get_tree().quit(0)
