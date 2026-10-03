extends Node

## Player options: window mode, window size and BGM/SFX volume. Saved to
## user://settings.cfg and applied on start.

signal changed

const WINDOWED := "windowed"
const BORDERLESS := "borderless"
const RESOLUTIONS: Array[Vector2i] = [
	Vector2i(1280, 720), Vector2i(1366, 768), Vector2i(1600, 900),
	Vector2i(1920, 1080), Vector2i(2560, 1440), Vector2i(3840, 2160),
]
const DEFAULT_RESOLUTION := Vector2i(1280, 720)
const BGM_BUS := "BGM"
const SFX_BUS := "SFX"

## Where the options are saved; tests point it elsewhere.
var settings_path := "user://settings.cfg"
var window_mode: String = WINDOWED
var resolution: Vector2i = DEFAULT_RESOLUTION
## Linear volume, 0.0 (muted) to 1.0.
var bgm_volume: float = 0.8
var sfx_volume: float = 0.8

var _preview_player: AudioStreamPlayer


func _ready() -> void:
	load_settings()
	apply_all()


func load_settings() -> void:
	var config := ConfigFile.new()
	if config.load(settings_path) != OK:
		return
	window_mode = str(config.get_value("display", "window_mode", WINDOWED))
	if window_mode not in [WINDOWED, BORDERLESS]:
		window_mode = WINDOWED
	var saved: Variant = config.get_value("display", "resolution", DEFAULT_RESOLUTION)
	resolution = saved if saved is Vector2i else DEFAULT_RESOLUTION
	bgm_volume = clampf(float(config.get_value("audio", "bgm_volume", bgm_volume)), 0.0, 1.0)
	sfx_volume = clampf(float(config.get_value("audio", "sfx_volume", sfx_volume)), 0.0, 1.0)


func save_settings() -> void:
	var config := ConfigFile.new()
	config.set_value("display", "window_mode", window_mode)
	config.set_value("display", "resolution", resolution)
	config.set_value("audio", "bgm_volume", bgm_volume)
	config.set_value("audio", "sfx_volume", sfx_volume)
	config.save(settings_path)


func reset_to_defaults() -> void:
	window_mode = WINDOWED
	resolution = DEFAULT_RESOLUTION
	bgm_volume = 0.8
	sfx_volume = 0.8
	apply_all()


func apply_all() -> void:
	apply_display()
	apply_audio()


func set_window_mode(mode: String) -> void:
	window_mode = mode if mode in [WINDOWED, BORDERLESS] else WINDOWED
	apply_display()


func set_resolution(size: Vector2i) -> void:
	resolution = size
	apply_display()


func set_bgm_volume(value: float) -> void:
	bgm_volume = clampf(value, 0.0, 1.0)
	apply_audio()


func set_sfx_volume(value: float) -> void:
	sfx_volume = clampf(value, 0.0, 1.0)
	apply_audio()


## Window sizes that fit on the current screen (always at least the default).
func available_resolutions() -> Array[Vector2i]:
	var screen := _screen_size()
	var result: Array[Vector2i] = []
	for size in RESOLUTIONS:
		if size == DEFAULT_RESOLUTION or (size.x <= screen.x and size.y <= screen.y):
			result.append(size)
	if resolution not in result:
		result.append(resolution)
	return result


## Borderless covers the whole screen at its native size; windowed uses `resolution`.
func apply_display() -> void:
	if DisplayServer.get_name() == "headless":
		changed.emit()
		return
	if window_mode == BORDERLESS:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
		DisplayServer.window_set_size(resolution)
		var screen := DisplayServer.window_get_current_screen()
		var origin := DisplayServer.screen_get_position(screen)
		var screen_size := DisplayServer.screen_get_size(screen)
		DisplayServer.window_set_position(origin + (screen_size - resolution) / 2)
	changed.emit()


func apply_audio() -> void:
	_set_bus_volume(BGM_BUS, bgm_volume)
	_set_bus_volume(SFX_BUS, sfx_volume)
	changed.emit()


## A short tone on the SFX bus so the player can hear the new volume.
func play_sfx_preview() -> void:
	if _preview_player == null:
		_preview_player = AudioStreamPlayer.new()
		_preview_player.bus = SFX_BUS
		_preview_player.stream = _preview_tone()
		add_child(_preview_player)
	_preview_player.play()


static func _set_bus_volume(bus_name: String, value: float) -> void:
	var bus := AudioServer.get_bus_index(bus_name)
	if bus < 0:
		return
	AudioServer.set_bus_mute(bus, value <= 0.001)
	AudioServer.set_bus_volume_db(bus, linear_to_db(maxf(value, 0.001)))


static func _screen_size() -> Vector2i:
	if DisplayServer.get_name() == "headless":
		return Vector2i(1920, 1080)
	return DisplayServer.screen_get_size(DisplayServer.window_get_current_screen())


static func _preview_tone() -> AudioStreamWAV:
	var mix_rate := 22050
	var samples := int(mix_rate * 0.12)
	var data := PackedByteArray()
	data.resize(samples * 2)
	for i in samples:
		var envelope := 1.0 - float(i) / samples
		var sample := int(sin(TAU * 880.0 * i / mix_rate) * envelope * 12000.0)
		data.encode_s16(i * 2, sample)
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = mix_rate
	stream.data = data
	return stream
