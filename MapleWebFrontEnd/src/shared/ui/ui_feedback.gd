extends Node

## Touch feedback for every tappable part (autoload "UiFeedback"): a ripple
## from the press point, clipped to the part's rounded shape, and a slight
## press-scale. Buttons get it automatically; custom tappable cards call
## UiFeedback.attach(card). Set the meta "no_feedback" on a node to opt out.

const PRESS_SCALE := 0.97


func _ready() -> void:
	get_tree().node_added.connect(_on_node_added)


func _on_node_added(node: Node) -> void:
	if node is BaseButton and not node.has_meta("no_feedback"):
		attach(node)


## Adds the ripple and press-scale to `control`. Safe to call twice.
func attach(control: Control, ripple_color: Color = Color.TRANSPARENT) -> void:
	if control.has_meta("_feedback"):
		return
	control.set_meta("_feedback", true)
	var ripple := Ripple.new()
	ripple.fixed_color = ripple_color
	control.add_child(ripple, false, Node.INTERNAL_MODE_BACK)
	control.gui_input.connect(_on_gui_input.bind(control, ripple))
	control.resized.connect(func(): control.pivot_offset = control.size / 2.0)
	control.pivot_offset = control.size / 2.0


func _on_gui_input(event: InputEvent, control: Control, ripple: Ripple) -> void:
	if not event is InputEventMouseButton or event.button_index != MOUSE_BUTTON_LEFT:
		return
	if control is BaseButton and control.disabled:
		return
	if event.pressed:
		ripple.start(event.position)
		_scale(control, PRESS_SCALE, M3.DURATION_SHORT * 0.7)
	else:
		ripple.release()
		_scale(control, 1.0, M3.DURATION_SHORT)


func _scale(control: Control, value: float, duration: float) -> void:
	if not control.is_inside_tree():
		return
	var tween := control.create_tween()
	M3.ease_tween(tween).tween_property(control, "scale", Vector2.ONE * value, duration)


## The expanding circle. Drawn over the part's content as a translucent state
## layer of the content color.
class Ripple:
	extends Control

	const OPACITY := 0.14
	const GROW_TIME := 0.4
	const FADE_TIME := 0.3

	var fixed_color := Color.TRANSPARENT
	var _center := Vector2.ZERO
	var _radius := 0.0
	var _alpha := 0.0
	var _tween: Tween

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_preset(Control.PRESET_FULL_RECT)

	func start(at: Vector2) -> void:
		_center = at
		var corners := [Vector2.ZERO, Vector2(size.x, 0), Vector2(0, size.y), size]
		var reach := 0.0
		for corner in corners:
			reach = maxf(reach, at.distance_to(corner))
		if _tween:
			_tween.kill()
		_radius = 0.0
		_alpha = OPACITY
		_tween = create_tween()
		M3.ease_tween(_tween).tween_method(_set_radius, 0.0, reach, GROW_TIME)

	func release() -> void:
		var fade := create_tween()
		fade.tween_interval(0.08)
		M3.ease_tween(fade).tween_method(_set_alpha, _alpha, 0.0, FADE_TIME)

	func _set_radius(value: float) -> void:
		_radius = value
		queue_redraw()

	func _set_alpha(value: float) -> void:
		_alpha = value
		queue_redraw()

	func _draw() -> void:
		if _alpha <= 0.001 or _radius <= 0.5:
			return
		var color := fixed_color
		if color.a <= 0.0:
			var host := get_parent() as Control
			color = host.get_theme_color("font_color") if host is Button else M3.ON_SURFACE
		color.a = _alpha
		# Both shapes are convex, so the intersection has no holes.
		for polygon in Geometry2D.intersect_polygons(_circle(), _shape()):
			draw_colored_polygon(polygon, color)

	func _circle() -> PackedVector2Array:
		var points := PackedVector2Array()
		for i in 40:
			points.append(_center + Vector2.from_angle(TAU * i / 40.0) * _radius)
		return points

	## The host's rounded rectangle, from its current stylebox.
	func _shape() -> PackedVector2Array:
		var radius := 0.0
		var host := get_parent() as Control
		var style: StyleBox = null
		if host is Button:
			style = host.get_theme_stylebox("normal")
		elif host is PanelContainer:
			style = host.get_theme_stylebox("panel")
		if style is StyleBoxFlat:
			radius = float(style.corner_radius_top_left)
		radius = minf(radius, minf(size.x, size.y) / 2.0)
		var points := PackedVector2Array()
		var corners := [
			[Vector2(size.x - radius, radius), -PI / 2.0],
			[Vector2(size.x - radius, size.y - radius), 0.0],
			[Vector2(radius, size.y - radius), PI / 2.0],
			[Vector2(radius, radius), PI],
		]
		for corner in corners:
			for step in 7:
				points.append(corner[0] + Vector2.from_angle(corner[1] + step * (PI / 2.0) / 6.0) * radius)
		return points
