extends SceneTree

## Builds src/shared/ui/main_theme.tres (and the Roboto font resources) from
## the M3 color roles in src/shared/ui/m3.gd. Run after changing a color:
##   godot --headless --path . --script tools/build_theme.gd

const THEME_PATH := "res://src/shared/ui/main_theme.tres"
const FONT_DIR := "res://src/shared/ui/fonts/"

var theme := Theme.new()


func _init() -> void:
	_build_fonts()
	var m3: GDScript = load("res://src/shared/ui/m3.gd")
	if m3 == null:
		push_error("m3.gd failed to load")
		quit(1)
		return
	_build(m3)
	var error := ResourceSaver.save(theme, THEME_PATH)
	print("THEME_SAVED" if error == OK else "THEME_SAVE_FAILED %d" % error)
	quit(0 if error == OK else 1)


func _build_fonts() -> void:
	DirAccess.make_dir_recursive_absolute(FONT_DIR)
	_save_font("roboto_regular.tres", "400", 0.0)
	_save_font("roboto_medium.tres", "400", 0.45)
	_save_font("roboto_bold.tres", "700", 0.0)


func _save_font(file_name: String, weight: String, embolden: float) -> void:
	var font := FontVariation.new()
	font.base_font = load("res://assets/fonts/roboto-latin-%s.woff2" % weight)
	font.fallbacks = [
		load("res://assets/fonts/roboto-latin-ext-%s.woff2" % weight),
		load("res://assets/fonts/roboto-vietnamese-%s.woff2" % weight),
	]
	font.variation_embolden = embolden
	ResourceSaver.save(font, FONT_DIR + file_name)


func _build(m: GDScript) -> void:
	var regular: Font = load(FONT_DIR + "roboto_regular.tres")
	var medium: Font = load(FONT_DIR + "roboto_medium.tres")
	theme.default_font = regular
	theme.default_font_size = m.BODY_MEDIUM

	# Text.
	theme.set_color("font_color", "Label", m.ON_SURFACE)
	_label_variation("MutedLabel", m.ON_SURFACE_VARIANT)
	_label_variation("AccentLabel", m.PRIMARY, medium)
	_label_variation("ErrorLabel", m.ERROR)
	_label_variation("SuccessLabel", m.SUCCESS)
	_label_variation("GoldLabel", m.GOLD, medium)
	_label_variation("EpicLabel", m.EPIC, medium)
	_label_variation("TitleLabel", m.ON_SURFACE, medium, m.TITLE_MEDIUM)
	_label_variation("HeadlineLabel", m.ON_SURFACE, null, m.HEADLINE_SMALL)
	theme.set_color("default_color", "RichTextLabel", m.ON_SURFACE)
	theme.set_font("bold_font", "RichTextLabel", load(FONT_DIR + "roboto_bold.tres"))
	theme.set_color("font_color", "LinkButton", m.PRIMARY)

	# Buttons. The default Button is the M3 filled tonal button; variations
	# cover filled (PrimaryButton), outlined, text and danger buttons.
	_button("Button", m.SECONDARY_CONTAINER, m.ON_SECONDARY_CONTAINER, m, medium)
	_button("PrimaryButton", m.PRIMARY, m.ON_PRIMARY, m, medium)
	_button("DangerButton", m.ERROR, m.ON_ERROR, m, medium)
	_button("OutlinedButton", Color.TRANSPARENT, m.PRIMARY, m, medium, m.OUTLINE_VARIANT)
	_button("TextButton", Color.TRANSPARENT, m.PRIMARY, m, medium)
	_toggle_button("ChipButton", m, medium, m.CORNER_SMALL, m.OUTLINE_VARIANT, Vector4(16, 8, 16, 8))
	_toggle_button("ListItemButton", m, medium, m.CORNER_FULL, Color.TRANSPARENT, Vector4(16, 10, 24, 10))
	_option_button(m, medium)
	_toggles(m)

	# Inputs.
	var field := _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_EXTRA_SMALL, Vector4(14, 10, 14, 10), m.OUTLINE, 1)
	var field_focus := _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_EXTRA_SMALL, Vector4(14, 10, 14, 10), m.PRIMARY, 2)
	var field_read_only := _box(m.with_alpha(m.ON_SURFACE, 0.04), m.CORNER_EXTRA_SMALL, Vector4(14, 10, 14, 10), m.with_alpha(m.ON_SURFACE, 0.12), 1)
	for type in ["LineEdit", "TextEdit"]:
		theme.set_stylebox("normal", type, field)
		theme.set_stylebox("focus", type, field_focus)
		theme.set_stylebox("read_only", type, field_read_only)
		theme.set_color("font_color", type, m.ON_SURFACE)
		theme.set_color("font_placeholder_color", type, m.ON_SURFACE_VARIANT)
		theme.set_color("font_readonly_color", type, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
		theme.set_color("caret_color", type, m.PRIMARY)
		theme.set_color("selection_color", type, m.with_alpha(m.PRIMARY, 0.25))
		theme.set_color("font_selected_color", type, m.ON_SURFACE)
	theme.set_font_size("font_size", "LineEdit", m.BODY_LARGE)

	# Containers. Cards sit on the hub's surfaceContainerHigh box, so they use
	# the lighter surface tones.
	theme.set_stylebox("panel", "PanelContainer", _box(m.SURFACE_CONTAINER_LOW, m.CORNER_CARD, Vector4(16, 16, 16, 16)))
	_variation("CompactPanel", "PanelContainer")
	theme.set_stylebox("panel", "CompactPanel", _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_MEDIUM, Vector4(12, 12, 12, 12)))
	_variation("TonalPanel", "PanelContainer")
	theme.set_stylebox("panel", "TonalPanel", _box(m.SURFACE_CONTAINER_HIGH, m.CORNER_EXTRA_LARGE, Vector4(20, 16, 20, 16)))
	_variation("OutlinedPanel", "PanelContainer")
	theme.set_stylebox("panel", "OutlinedPanel", _box(m.SURFACE, m.CORNER_MEDIUM, Vector4(12, 12, 12, 12), m.OUTLINE_VARIANT, 1))
	_variation("DialogPanel", "PanelContainer")
	theme.set_stylebox("panel", "DialogPanel", _box(m.SURFACE_CONTAINER_HIGH, m.CORNER_EXTRA_LARGE, Vector4(24, 24, 24, 24)))
	_variation("AvatarPanel", "PanelContainer")
	theme.set_stylebox("panel", "AvatarPanel", _box(m.SURFACE_CONTAINER_HIGHEST, m.CORNER_CARD, Vector4.ZERO))
	_variation("IconPanel", "PanelContainer")
	theme.set_stylebox("panel", "IconPanel", _box(m.SURFACE_CONTAINER_HIGHEST, m.CORNER_MEDIUM, Vector4(8, 8, 8, 8)))
	theme.set_stylebox("panel", "TabContainer", StyleBoxEmpty.new())
	theme.set_stylebox("panel", "Panel", _box(m.SURFACE_CONTAINER_LOW, m.CORNER_CARD, Vector4.ZERO))
	_tabs(m, medium)

	# Separators.
	var line := StyleBoxLine.new()
	line.color = m.OUTLINE_VARIANT
	line.thickness = 1
	theme.set_stylebox("separator", "HSeparator", line)
	var vline := StyleBoxLine.new()
	vline.color = m.OUTLINE_VARIANT
	vline.thickness = 1
	vline.vertical = true
	theme.set_stylebox("separator", "VSeparator", vline)

	# Lists and menus.
	var popup := _box(m.SURFACE_CONTAINER, m.CORNER_EXTRA_SMALL, Vector4(0, 8, 0, 8))
	popup.shadow_color = m.with_alpha(Color.BLACK, 0.18)
	popup.shadow_size = 6
	popup.shadow_offset = Vector2(0, 2)
	theme.set_stylebox("panel", "PopupPanel", popup)
	theme.set_stylebox("panel", "PopupMenu", popup)
	theme.set_stylebox("hover", "PopupMenu", _box(m.with_alpha(m.ON_SURFACE, m.HOVER_OPACITY), 0, Vector4(12, 8, 12, 8)))
	theme.set_color("font_color", "PopupMenu", m.ON_SURFACE)
	theme.set_color("font_hover_color", "PopupMenu", m.ON_SURFACE)
	theme.set_color("font_disabled_color", "PopupMenu", m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
	theme.set_color("font_separator_color", "PopupMenu", m.ON_SURFACE_VARIANT)
	theme.set_constant("v_separation", "PopupMenu", 10)
	theme.set_constant("item_start_padding", "PopupMenu", 12)
	theme.set_constant("item_end_padding", "PopupMenu", 12)
	theme.set_stylebox("panel", "ItemList", _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_MEDIUM, Vector4(6, 6, 6, 6)))
	theme.set_stylebox("focus", "ItemList", StyleBoxEmpty.new())
	theme.set_stylebox("selected", "ItemList", _box(m.SECONDARY_CONTAINER, m.CORNER_FULL, Vector4(10, 6, 10, 6)))
	theme.set_stylebox("selected_focus", "ItemList", _box(m.SECONDARY_CONTAINER, m.CORNER_FULL, Vector4(10, 6, 10, 6)))
	theme.set_stylebox("hovered", "ItemList", _box(m.with_alpha(m.ON_SURFACE, m.HOVER_OPACITY), m.CORNER_FULL, Vector4(10, 6, 10, 6)))
	theme.set_stylebox("hovered_selected", "ItemList", _box(m.layered(m.SECONDARY_CONTAINER, m.ON_SECONDARY_CONTAINER, m.HOVER_OPACITY), m.CORNER_FULL, Vector4(10, 6, 10, 6)))
	theme.set_stylebox("cursor", "ItemList", StyleBoxEmpty.new())
	theme.set_stylebox("cursor_unfocused", "ItemList", StyleBoxEmpty.new())
	theme.set_color("font_color", "ItemList", m.ON_SURFACE)
	theme.set_color("font_hovered_color", "ItemList", m.ON_SURFACE)
	theme.set_color("font_selected_color", "ItemList", m.ON_SECONDARY_CONTAINER)
	theme.set_color("font_hovered_selected_color", "ItemList", m.ON_SECONDARY_CONTAINER)
	theme.set_color("guide_color", "ItemList", Color.TRANSPARENT)
	theme.set_constant("v_separation", "ItemList", 6)

	# Dialogs (AcceptDialog / ConfirmationDialog are embedded windows).
	var window := _box(m.SURFACE_CONTAINER_HIGH, m.CORNER_EXTRA_LARGE, Vector4(24, 20, 24, 20))
	window.expand_margin_top = 44
	window.expand_margin_left = 8
	window.expand_margin_right = 8
	window.expand_margin_bottom = 8
	window.shadow_color = m.with_alpha(Color.BLACK, 0.2)
	window.shadow_size = 12
	window.shadow_offset = Vector2(0, 4)
	theme.set_stylebox("embedded_border", "Window", window)
	theme.set_stylebox("embedded_unfocused_border", "Window", window)
	theme.set_color("title_color", "Window", m.ON_SURFACE)
	theme.set_font("title_font", "Window", regular)
	theme.set_font_size("title_font_size", "Window", m.HEADLINE_SMALL)
	theme.set_constant("title_height", "Window", 40)
	theme.set_stylebox("panel", "AcceptDialog", StyleBoxEmpty.new())
	theme.set_constant("buttons_separation", "AcceptDialog", 8)

	# Progress and sliders: the M3 Expressive thick track.
	theme.set_stylebox("background", "ProgressBar", _box(m.SECONDARY_CONTAINER, m.CORNER_FULL, Vector4.ZERO))
	theme.set_stylebox("fill", "ProgressBar", _box(m.PRIMARY, m.CORNER_FULL, Vector4.ZERO))
	theme.set_color("font_color", "ProgressBar", m.ON_SURFACE)
	theme.set_color("font_outline_color", "ProgressBar", m.SURFACE_CONTAINER_LOWEST)
	theme.set_constant("outline_size", "ProgressBar", 3)
	for pair in [["HPBar", m.HP], ["MPBar", m.MP], ["EXPBar", m.EXP], ["EnemyHPBar", m.ENEMY_HP]]:
		_variation(pair[0], "ProgressBar")
		theme.set_stylebox("fill", pair[0], _box(pair[1], m.CORNER_FULL, Vector4.ZERO))
		theme.set_stylebox("background", pair[0], _box(m.SURFACE_CONTAINER_HIGHEST, m.CORNER_FULL, Vector4.ZERO))
	var track := _box(m.SECONDARY_CONTAINER, m.CORNER_SMALL, Vector4(0, 8, 0, 8))
	var track_fill := _box(m.PRIMARY, m.CORNER_SMALL, Vector4(0, 8, 0, 8))
	theme.set_stylebox("slider", "HSlider", track)
	theme.set_stylebox("grabber_area", "HSlider", track_fill)
	theme.set_stylebox("grabber_area_highlight", "HSlider", track_fill)
	theme.set_icon("grabber", "HSlider", _handle_texture(m.PRIMARY))
	theme.set_icon("grabber_highlight", "HSlider", _handle_texture(m.PRIMARY))
	theme.set_icon("grabber_disabled", "HSlider", _handle_texture(m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY)))
	theme.set_constant("center_grabber", "HSlider", 1)

	# Scrollbars.
	for type in ["VScrollBar", "HScrollBar"]:
		var vertical: bool = type == "VScrollBar"
		var margin := Vector4(4, 2, 4, 2) if vertical else Vector4(2, 4, 2, 4)
		var scroll_track := _box(Color.TRANSPARENT, m.CORNER_FULL, margin)
		theme.set_stylebox("scroll", type, scroll_track)
		theme.set_stylebox("scroll_focus", type, scroll_track)
		theme.set_stylebox("grabber", type, _box(m.with_alpha(m.ON_SURFACE_VARIANT, 0.35), m.CORNER_FULL, Vector4(3, 3, 3, 3)))
		theme.set_stylebox("grabber_highlight", type, _box(m.with_alpha(m.ON_SURFACE_VARIANT, 0.55), m.CORNER_FULL, Vector4(3, 3, 3, 3)))
		theme.set_stylebox("grabber_pressed", type, _box(m.with_alpha(m.ON_SURFACE_VARIANT, 0.7), m.CORNER_FULL, Vector4(3, 3, 3, 3)))

	# Tooltips (the built-in ones; item tooltips draw their own card).
	theme.set_stylebox("panel", "TooltipPanel", _box(m.INVERSE_SURFACE, m.CORNER_EXTRA_SMALL, Vector4(8, 4, 8, 4)))
	theme.set_color("font_color", "TooltipLabel", m.INVERSE_ON_SURFACE)
	theme.set_font_size("font_size", "TooltipLabel", m.BODY_SMALL)


func _label_variation(name: String, color: Color, font: Font = null, size: int = 0) -> void:
	_variation(name, "Label")
	theme.set_color("font_color", name, color)
	if font != null:
		theme.set_font("font", name, font)
	if size > 0:
		theme.set_font_size("font_size", name, size)


func _variation(name: String, base: String) -> void:
	theme.set_type_variation(name, base)


## A pill button with state layers on its container.
func _button(type: String, container: Color, content: Color, m: GDScript, font: Font, border: Color = Color.TRANSPARENT) -> void:
	if type != "Button":
		_variation(type, "Button")
	var padding := Vector4(24, 10, 24, 10) if container.a > 0.0 or border.a > 0.0 else Vector4(12, 10, 12, 10)
	var hover_color: Color = m.layered(container, content, m.HOVER_OPACITY) if container.a > 0.0 else m.with_alpha(content, m.HOVER_OPACITY)
	var press_color: Color = m.layered(container, content, m.PRESS_OPACITY + 0.04) if container.a > 0.0 else m.with_alpha(content, m.PRESS_OPACITY + 0.02)
	theme.set_stylebox("normal", type, _box(container, m.CORNER_FULL, padding, border, 1))
	theme.set_stylebox("hover", type, _box(hover_color, m.CORNER_FULL, padding, border, 1))
	theme.set_stylebox("pressed", type, _box(press_color, m.CORNER_FULL, padding, border, 1))
	theme.set_stylebox("hover_pressed", type, _box(press_color, m.CORNER_FULL, padding, border, 1))
	var disabled_container: Color = m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTAINER_OPACITY) if container.a > 0.0 else Color.TRANSPARENT
	var disabled_border: Color = m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTAINER_OPACITY) if border.a > 0.0 else Color.TRANSPARENT
	theme.set_stylebox("disabled", type, _box(disabled_container, m.CORNER_FULL, padding, disabled_border, 1))
	var focus := _box(Color.TRANSPARENT, m.CORNER_FULL, padding, m.SECONDARY, 3)
	focus.draw_center = false
	focus.expand_margin_left = 2
	focus.expand_margin_right = 2
	focus.expand_margin_top = 2
	focus.expand_margin_bottom = 2
	theme.set_stylebox("focus", type, focus)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		theme.set_color(state, type, content)
	theme.set_color("font_disabled_color", type, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
	for state in ["icon_normal_color", "icon_hover_color", "icon_pressed_color", "icon_focus_color", "icon_hover_pressed_color"]:
		theme.set_color(state, type, content)
	theme.set_color("icon_disabled_color", type, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
	theme.set_font("font", type, font)
	theme.set_font_size("font_size", type, m.LABEL_LARGE)
	theme.set_constant("h_separation", type, 8)


## Toggle buttons: ChipButton is an M3 filter chip (outlined until selected),
## ListItemButton a navigation-drawer item (a pill shows when selected).
func _toggle_button(type: String, m: GDScript, font: Font, radius: int, border: Color, padding: Vector4) -> void:
	_variation(type, "Button")
	var on: Color = m.SECONDARY_CONTAINER
	theme.set_stylebox("normal", type, _box(Color.TRANSPARENT, radius, padding, border, 1))
	theme.set_stylebox("hover", type, _box(m.with_alpha(m.ON_SURFACE, m.HOVER_OPACITY), radius, padding, border, 1))
	theme.set_stylebox("pressed", type, _box(on, radius, padding))
	theme.set_stylebox("hover_pressed", type, _box(m.layered(on, m.ON_SECONDARY_CONTAINER, m.HOVER_OPACITY), radius, padding))
	theme.set_stylebox("disabled", type, _box(Color.TRANSPARENT, radius, padding, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTAINER_OPACITY) if border.a > 0.0 else Color.TRANSPARENT, 1))
	var focus := _box(Color.TRANSPARENT, radius, padding, m.SECONDARY, 3)
	focus.draw_center = false
	theme.set_stylebox("focus", type, focus)
	theme.set_color("font_color", type, m.ON_SURFACE_VARIANT)
	theme.set_color("font_hover_color", type, m.ON_SURFACE)
	theme.set_color("font_focus_color", type, m.ON_SURFACE_VARIANT)
	theme.set_color("font_pressed_color", type, m.ON_SECONDARY_CONTAINER)
	theme.set_color("font_hover_pressed_color", type, m.ON_SECONDARY_CONTAINER)
	theme.set_color("font_disabled_color", type, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
	theme.set_font("font", type, font)
	theme.set_font_size("font_size", type, m.LABEL_LARGE)


## Dropdowns look like M3 outlined menus.
func _option_button(m: GDScript, font: Font) -> void:
	var padding := Vector4(16, 10, 16, 10)
	theme.set_stylebox("normal", "OptionButton", _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_EXTRA_SMALL, padding, m.OUTLINE, 1))
	theme.set_stylebox("hover", "OptionButton", _box(m.layered(m.SURFACE_CONTAINER_LOWEST, m.ON_SURFACE, m.HOVER_OPACITY), m.CORNER_EXTRA_SMALL, padding, m.ON_SURFACE, 1))
	theme.set_stylebox("pressed", "OptionButton", _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_EXTRA_SMALL, padding, m.PRIMARY, 2))
	theme.set_stylebox("hover_pressed", "OptionButton", _box(m.SURFACE_CONTAINER_LOWEST, m.CORNER_EXTRA_SMALL, padding, m.PRIMARY, 2))
	theme.set_stylebox("disabled", "OptionButton", _box(Color.TRANSPARENT, m.CORNER_EXTRA_SMALL, padding, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTAINER_OPACITY), 1))
	var focus := _box(Color.TRANSPARENT, m.CORNER_EXTRA_SMALL, padding, m.PRIMARY, 2)
	focus.draw_center = false
	theme.set_stylebox("focus", "OptionButton", focus)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		theme.set_color(state, "OptionButton", m.ON_SURFACE)
	theme.set_color("font_disabled_color", "OptionButton", m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
	theme.set_font_size("font_size", "OptionButton", m.BODY_LARGE)
	theme.set_constant("arrow_margin", "OptionButton", 12)
	theme.set_icon("arrow", "OptionButton", _arrow_texture(m.ON_SURFACE_VARIANT))
	theme.set_color("modulate_arrow", "OptionButton", Color.WHITE)


func _toggles(m: GDScript) -> void:
	for type in ["CheckBox", "CheckButton"]:
		var empty := StyleBoxEmpty.new()
		empty.content_margin_left = 4
		empty.content_margin_right = 4
		empty.content_margin_top = 6
		empty.content_margin_bottom = 6
		for state in ["normal", "pressed", "disabled", "hover_pressed", "focus"]:
			theme.set_stylebox(state, type, empty)
		theme.set_stylebox("hover", type, _box(m.with_alpha(m.ON_SURFACE, m.HOVER_OPACITY), m.CORNER_FULL, Vector4(4, 6, 4, 6)))
		for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
			theme.set_color(state, type, m.ON_SURFACE)
		theme.set_color("font_disabled_color", type, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))


## M3 primary tabs: label on the surface, a 3dp primary indicator under the
## selected one.
func _tabs(m: GDScript, font: Font) -> void:
	var unselected := _box(Color.TRANSPARENT, 0, Vector4(16, 12, 16, 12))
	var hovered := _box(m.with_alpha(m.ON_SURFACE, m.HOVER_OPACITY), m.CORNER_SMALL, Vector4(16, 12, 16, 12))
	var selected := _box(Color.TRANSPARENT, 0, Vector4(16, 12, 16, 12), m.PRIMARY, 0)
	selected.border_width_bottom = 3
	selected.border_color = m.PRIMARY
	for type in ["TabBar", "TabContainer"]:
		theme.set_stylebox("tab_unselected", type, unselected)
		theme.set_stylebox("tab_hovered", type, hovered)
		theme.set_stylebox("tab_selected", type, selected)
		theme.set_stylebox("tab_disabled", type, unselected)
		theme.set_stylebox("tab_focus", type, StyleBoxEmpty.new())
		theme.set_color("font_selected_color", type, m.PRIMARY)
		theme.set_color("font_hovered_color", type, m.ON_SURFACE)
		theme.set_color("font_unselected_color", type, m.ON_SURFACE_VARIANT)
		theme.set_color("font_disabled_color", type, m.with_alpha(m.ON_SURFACE, m.DISABLED_CONTENT_OPACITY))
		theme.set_font("font", type, font)
		theme.set_font_size("font_size", type, m.TITLE_SMALL)
	var bar := _box(Color.TRANSPARENT, 0, Vector4.ZERO, m.SURFACE_CONTAINER_HIGHEST, 0)
	bar.border_width_bottom = 1
	theme.set_stylebox("tabbar_background", "TabContainer", bar)


func _box(color: Color, radius: int, padding: Vector4, border: Color = Color.TRANSPARENT, border_width: int = 1) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(radius)
	style.corner_detail = 12
	style.anti_aliasing = true
	style.content_margin_left = padding.x
	style.content_margin_top = padding.y
	style.content_margin_right = padding.z
	style.content_margin_bottom = padding.w
	if border.a > 0.0 and border_width > 0:
		style.border_color = border
		style.set_border_width_all(border_width)
	return style


## The M3 Expressive slider handle: a 4×44dp rounded bar, with a gap of the
## surface around it so it reads apart from the track.
func _handle_texture(color: Color) -> ImageTexture:
	var image := Image.create(12, 44, false, Image.FORMAT_RGBA8)
	image.fill(Color.TRANSPARENT)
	for y in 44:
		for x in range(4, 8):
			var edge := minf(y, 43 - y)
			var alpha := 1.0 if edge >= 2.0 else (0.6 if edge >= 1.0 else 0.25)
			if x == 4 or x == 7:
				alpha *= 0.85
			image.set_pixel(x, y, Color(color.r, color.g, color.b, color.a * alpha))
	return ImageTexture.create_from_image(image)


## The dropdown chevron.
func _arrow_texture(color: Color) -> ImageTexture:
	var image := Image.create(12, 8, false, Image.FORMAT_RGBA8)
	image.fill(Color.TRANSPARENT)
	for y in 6:
		for x in range(y, 11 - y):
			image.set_pixel(x, y + 1, color)
	return ImageTexture.create_from_image(image)
