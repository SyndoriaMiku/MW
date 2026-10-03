extends Node

## The options panel changes GameSettings, the audio buses follow, and the
## options survive a save and load.

const TEST_PATH := "user://test_settings.cfg"


func _ready() -> void:
	var real_path := GameSettings.settings_path
	GameSettings.settings_path = TEST_PATH
	var ok := await _check()
	GameSettings.settings_path = real_path
	DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))
	if ok:
		print("SETTINGS_OK")
		get_tree().quit(0)


func _check() -> bool:
	for bus in [GameSettings.BGM_BUS, GameSettings.SFX_BUS]:
		if AudioServer.get_bus_index(bus) < 0:
			return _fail("AUDIO_BUS_MISSING %s" % bus)

	var panel := SettingsPanel.open(self)
	await get_tree().process_frame
	panel.bgm_slider.value = 0
	panel.sfx_slider.value = 50
	var bgm_bus := AudioServer.get_bus_index(GameSettings.BGM_BUS)
	var sfx_bus := AudioServer.get_bus_index(GameSettings.SFX_BUS)
	if not AudioServer.is_bus_mute(bgm_bus) or panel.bgm_value.text != "Muted":
		return _fail("BGM_MUTE_FAILED")
	if AudioServer.is_bus_mute(sfx_bus) or absf(AudioServer.get_bus_volume_db(sfx_bus) - linear_to_db(0.5)) > 0.01 or panel.sfx_value.text != "50%":
		return _fail("SFX_VOLUME_FAILED %s" % AudioServer.get_bus_volume_db(sfx_bus))

	panel.mode_select.select(1)
	panel.mode_select.item_selected.emit(1)
	if GameSettings.window_mode != GameSettings.BORDERLESS or not panel.resolution_select.disabled:
		return _fail("BORDERLESS_MODE_FAILED")
	panel.mode_select.select(0)
	panel.mode_select.item_selected.emit(0)
	var last := panel.resolution_select.item_count - 1
	panel.resolution_select.select(last)
	panel.resolution_select.item_selected.emit(last)
	var chosen := GameSettings.resolution
	if panel.resolution_select.disabled or chosen != panel._resolutions[last]:
		return _fail("RESOLUTION_FAILED")
	panel.close()

	GameSettings.bgm_volume = 1.0
	GameSettings.sfx_volume = 1.0
	GameSettings.resolution = Vector2i(1, 1)
	GameSettings.load_settings()
	if GameSettings.bgm_volume != 0.0 or not is_equal_approx(GameSettings.sfx_volume, 0.5) or GameSettings.resolution != chosen or GameSettings.window_mode != GameSettings.WINDOWED:
		return _fail("SETTINGS_NOT_SAVED %s %s %s" % [GameSettings.bgm_volume, GameSettings.sfx_volume, GameSettings.resolution])
	GameSettings.reset_to_defaults()
	if GameSettings.resolution != GameSettings.DEFAULT_RESOLUTION or GameSettings.window_mode != GameSettings.WINDOWED:
		return _fail("RESET_FAILED")
	return true


func _fail(code: String) -> bool:
	printerr(code)
	get_tree().quit(1)
	return false
