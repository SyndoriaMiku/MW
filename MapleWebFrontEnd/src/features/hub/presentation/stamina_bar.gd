class_name StaminaBar
extends Control

## A read-only progress bar: a rounded secondaryContainer track with a primary
## fill that glides to new values.

const TRACK_HEIGHT := 12.0

var ratio := 0.0:
	set(value):
		ratio = clampf(value, 0.0, 1.0)
		queue_redraw()

var _tween: Tween


func _init() -> void:
	custom_minimum_size = Vector2(120, TRACK_HEIGHT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func set_value(value: float, maximum: float, animate: bool = true) -> void:
	var target := value / maximum if maximum > 0.0 else 0.0
	if _tween:
		_tween.kill()
	if not animate or not is_inside_tree():
		ratio = target
		return
	_tween = create_tween()
	M3.ease_tween(_tween).tween_property(self, "ratio", target, M3.DURATION_LONG)


func _draw() -> void:
	var track := Rect2(0, (size.y - TRACK_HEIGHT) / 2.0, size.x, TRACK_HEIGHT)
	_draw_pill(track, M3.SECONDARY_CONTAINER)
	var fill_width := size.x * ratio
	if fill_width > 0.5:
		_draw_pill(Rect2(track.position, Vector2(maxf(fill_width, TRACK_HEIGHT), TRACK_HEIGHT)), M3.PRIMARY)


func _draw_pill(rect: Rect2, color: Color) -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(int(TRACK_HEIGHT / 2.0))
	style.corner_detail = 8
	style.anti_aliasing = true
	draw_style_box(style, rect)
