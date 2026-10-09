class_name HubWidgets
extends RefCounted

## Building blocks shared by the hub's own pages (Adventure, Quests, Skills):
## the page header, list cards, chips and the detail card.


## A page's outer margin and column; returns the column.
static func page_column(page: Control) -> VBoxContainer:
	var margin := MarginContainer.new()
	margin.name = "Margin"
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 20)
	page.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	margin.add_child(column)
	return column


## Title, a status line and a Refresh text button that clears the cache first.
## Returns {"row", "status", "refresh"}.
static func header(title_text: String, on_refresh: Callable) -> Dictionary:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	var title := Label.new()
	title.text = title_text
	title.theme_type_variation = &"HeadlineLabel"
	row.add_child(title)
	var status := Label.new()
	status.name = "Status"
	status.theme_type_variation = &"MutedLabel"
	status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	status.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(status)
	var refresh := Button.new()
	refresh.name = "RefreshButton"
	refresh.text = "Refresh"
	refresh.theme_type_variation = &"TextButton"
	refresh.icon = IconTexture.make("refresh", M3.PRIMARY, 20)
	refresh.pressed.connect(func():
		GameCache.clear_all()
		on_refresh.call()
	)
	row.add_child(refresh)
	return {"row": row, "status": status, "refresh": refresh}


## A selectable list row: icon badge, title, a meta line and an optional
## trailing tag. `locked` greys it out.
static func list_card(icon_name: String, title_text: String, meta_text: String, selected: bool, locked: bool, tag_text: String = "", tag_color: Color = M3.PRIMARY) -> Button:
	var card := Button.new()
	card.custom_minimum_size = Vector2(0, 68)
	card.toggle_mode = true
	card.button_pressed = selected
	card.focus_mode = Control.FOCUS_NONE
	var base := M3.SECONDARY_CONTAINER if selected else M3.SURFACE_CONTAINER_LOWEST
	var content := M3.ON_SECONDARY_CONTAINER if selected else M3.ON_SURFACE
	for state in ["normal", "hover", "pressed", "hover_pressed"]:
		var opacity := M3.HOVER_OPACITY if state.begins_with("hover") else 0.0
		card.add_theme_stylebox_override(state, M3.box(M3.layered(base, content, opacity), M3.CORNER_LARGE, 12.0))
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 10)
	row.add_theme_constant_override("separation", 12)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(row)
	row.add_child(badge(icon_name, M3.SURFACE_CONTAINER_HIGHEST if locked else M3.PRIMARY_CONTAINER, M3.ON_SURFACE_VARIANT if locked else M3.ON_PRIMARY_CONTAINER, 46))
	var text := VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.alignment = BoxContainer.ALIGNMENT_CENTER
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_theme_constant_override("separation", 2)
	row.add_child(text)
	var title := Label.new()
	title.text = title_text
	title.theme_type_variation = &"TitleLabel"
	title.add_theme_color_override("font_color", content if not locked else M3.with_alpha(M3.ON_SURFACE, 0.6))
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(title)
	var meta := Label.new()
	meta.text = meta_text
	meta.theme_type_variation = &"MutedLabel"
	meta.add_theme_font_size_override("font_size", M3.BODY_SMALL)
	meta.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	meta.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_child(meta)
	if not tag_text.is_empty():
		row.add_child(tag(tag_text, tag_color))
	return card


## A rounded icon badge.
static func badge(icon_name: String, background: Color, foreground: Color, size: int = 44) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(size, size)
	panel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", M3.box(background, M3.CORNER_MEDIUM, 0.0))
	panel.add_child(M3.icon_label(icon_name, int(size * 0.52), foreground))
	return panel


## A small filled label, e.g. "Ready" or "Daily".
static func tag(text: String, color: Color) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := M3.box(M3.with_alpha(color, 0.14), M3.CORNER_SMALL, 0.0)
	style.content_margin_left = 8
	style.content_margin_right = 8
	style.content_margin_top = 3
	style.content_margin_bottom = 3
	panel.add_theme_stylebox_override("panel", style)
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", M3.FONT_MEDIUM)
	label.add_theme_font_size_override("font_size", M3.LABEL_MEDIUM)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(label)
	return panel


## An outlined assist chip with an icon; returns {"chip", "label"}.
static func chip(icon_name: String, text: String = "") -> Dictionary:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", M3.box(Color.TRANSPARENT, M3.CORNER_SMALL, 6.0, M3.OUTLINE_VARIANT))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	panel.add_child(row)
	row.add_child(M3.icon_label(icon_name, 18, M3.PRIMARY))
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", M3.FONT_MEDIUM)
	label.add_theme_font_size_override("font_size", M3.LABEL_LARGE)
	label.add_theme_color_override("font_color", M3.ON_SURFACE_VARIANT)
	row.add_child(label)
	return {"chip": panel, "label": label}


## The white detail card on the right of a list page; returns its column.
static func detail_card(parent: Control) -> VBoxContainer:
	var card := PanelContainer.new()
	card.name = "DetailCard"
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", M3.box(M3.SURFACE_CONTAINER_LOWEST, M3.CORNER_EXTRA_LARGE, 24.0))
	parent.add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	card.add_child(column)
	return column


## A vertical list inside a scroll container of `width` (0 = expand).
static func scroll_list(parent: Control, width: float) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	if width > 0.0:
		scroll.custom_minimum_size = Vector2(width, 0)
	else:
		scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 8)
	scroll.add_child(list)
	return list


## A small section heading inside a list.
static func section_label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = &"AccentLabel"
	label.add_theme_font_size_override("font_size", M3.LABEL_LARGE)
	return label


## Empties `container`. Nodes in `keep` are only taken out, so they can be
## added again.
static func clear(container: Node, keep: Array = []) -> void:
	for child in container.get_children():
		container.remove_child(child)
		if not keep.has(child):
			child.queue_free()
