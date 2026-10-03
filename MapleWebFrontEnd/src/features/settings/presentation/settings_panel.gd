class_name SettingsPanel
extends Control

## Options overlay: window mode, resolution, BGM and SFX volume. Changes apply
## immediately; closing the panel saves them.

const SCENE := preload("res://src/features/settings/presentation/settings_panel.tscn")
const MODE_LABELS := {"windowed": "Windowed", "borderless": "Borderless fullscreen"}

@onready var mode_select: OptionButton = %ModeSelect
@onready var resolution_select: OptionButton = %ResolutionSelect
@onready var resolution_hint: Label = %ResolutionHint
@onready var bgm_slider: HSlider = %BgmSlider
@onready var bgm_value: Label = %BgmValue
@onready var sfx_slider: HSlider = %SfxSlider
@onready var sfx_value: Label = %SfxValue
@onready var reset_button: Button = %ResetButton
@onready var close_button: Button = %CloseButton

var _resolutions: Array[Vector2i] = []


## Shows the panel on top of `host` (usually the current screen).
static func open(host: Node) -> SettingsPanel:
	var panel: SettingsPanel = SCENE.instantiate()
	host.add_child(panel)
	return panel


func _ready() -> void:
	for mode in MODE_LABELS:
		mode_select.add_item(MODE_LABELS[mode])
		mode_select.set_item_metadata(mode_select.item_count - 1, mode)
	mode_select.item_selected.connect(_on_mode_selected)
	resolution_select.item_selected.connect(_on_resolution_selected)
	bgm_slider.value_changed.connect(_on_bgm_changed)
	sfx_slider.value_changed.connect(_on_sfx_changed)
	sfx_slider.drag_ended.connect(func(_changed): GameSettings.play_sfx_preview())
	reset_button.pressed.connect(_on_reset_pressed)
	close_button.pressed.connect(close)
	_render()
	close_button.grab_focus()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		close()


func close() -> void:
	GameSettings.save_settings()
	queue_free()


func _render() -> void:
	for index in mode_select.item_count:
		if mode_select.get_item_metadata(index) == GameSettings.window_mode:
			mode_select.select(index)
	resolution_select.clear()
	_resolutions = GameSettings.available_resolutions()
	for size in _resolutions:
		resolution_select.add_item("%d × %d" % [size.x, size.y])
		if size == GameSettings.resolution:
			resolution_select.select(resolution_select.item_count - 1)
	var borderless := GameSettings.window_mode == GameSettings.BORDERLESS
	resolution_select.disabled = borderless
	resolution_hint.text = "Borderless fullscreen uses your screen's resolution." if borderless else "Size of the game window."
	bgm_slider.set_value_no_signal(GameSettings.bgm_volume * 100.0)
	sfx_slider.set_value_no_signal(GameSettings.sfx_volume * 100.0)
	bgm_value.text = volume_text(GameSettings.bgm_volume)
	sfx_value.text = volume_text(GameSettings.sfx_volume)


static func volume_text(value: float) -> String:
	return "Muted" if value <= 0.001 else "%d%%" % roundi(value * 100.0)


func _on_mode_selected(index: int) -> void:
	GameSettings.set_window_mode(str(mode_select.get_item_metadata(index)))
	_render()


func _on_resolution_selected(index: int) -> void:
	if index >= 0 and index < _resolutions.size():
		GameSettings.set_resolution(_resolutions[index])


func _on_bgm_changed(value: float) -> void:
	GameSettings.set_bgm_volume(value / 100.0)
	bgm_value.text = volume_text(GameSettings.bgm_volume)


func _on_sfx_changed(value: float) -> void:
	GameSettings.set_sfx_volume(value / 100.0)
	sfx_value.text = volume_text(GameSettings.sfx_volume)


func _on_reset_pressed() -> void:
	GameSettings.reset_to_defaults()
	_render()
