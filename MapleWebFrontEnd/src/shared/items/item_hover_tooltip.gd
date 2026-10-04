class_name ItemHoverTooltip
extends PanelContainer

## A tooltip that follows the mouse. Equipment shows side by side with the
## equipped item it would replace, plus the stat change; other items show their
## description. It ignores the mouse so clicks reach the item underneath.

const COLUMN_WIDTH := 300.0
const OFFSET := Vector2(18, 14)

var _content := VBoxContainer.new()
var _mouse_position := Vector2.ZERO


func _init() -> void:
	top_level = true
	z_index = 100
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := M3.box(M3.SURFACE_CONTAINER, M3.CORNER_MEDIUM, 16.0)
	style.shadow_color = M3.with_alpha(Color.BLACK, 0.2)
	style.shadow_size = 8
	style.shadow_offset = Vector2(0, 3)
	add_theme_stylebox_override("panel", style)
	_content.add_theme_constant_override("separation", 10)
	add_child(_content)


## Shows `item` next to `compare` (an equipped item of the same type, {} for
## none) captioned `compare_caption`. When `outcome` is set, a stat change
## section follows: what equipping does, measured against `replaced` ({} when
## it goes into a free slot). An equipped `item` passes no outcome.
func show_equipment(item: Dictionary, compare: Dictionary, compare_caption: String, outcome: String, replaced: Dictionary, equipped_items: Array, hint: String) -> void:
	_clear()
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 16)
	_content.add_child(columns)
	columns.add_child(_equipment_column(item, "", "IN YOUR BAG" if not outcome.is_empty() else "CURRENTLY EQUIPPED", equipped_items))
	if not compare.is_empty():
		columns.add_child(VSeparator.new())
		columns.add_child(_equipment_column(compare, compare_caption, "CURRENTLY EQUIPPED", equipped_items))
	if not outcome.is_empty():
		_content.add_child(HSeparator.new())
		_content.add_child(ItemTooltip.label("IF YOU EQUIP IT  (%s)" % outcome, 13, M3.ON_SURFACE_VARIANT))
		var changes := RichTextLabel.new()
		changes.bbcode_enabled = true
		changes.fit_content = true
		changes.scroll_active = false
		changes.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
		changes.text = ItemTooltip.stat_changes_bbcode(ItemTooltip.stat_changes(item, replaced))
		_content.add_child(changes)
	_add_hint(hint)
	_finish()


func show_simple(item: Dictionary, hint: String) -> void:
	_clear()
	var column := VBoxContainer.new()
	column.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
	column.add_theme_constant_override("separation", 7)
	_content.add_child(column)
	ItemTooltip.fill_simple(column, item, "")
	_add_hint(hint)
	_finish()


func hide_tooltip() -> void:
	visible = false


## Places the tooltip next to the mouse, inside the viewport.
func follow(mouse_position: Vector2) -> void:
	_mouse_position = mouse_position
	var viewport_size := get_viewport_rect().size
	var tooltip_size := get_combined_minimum_size()
	var target := mouse_position + OFFSET
	if target.x + tooltip_size.x > viewport_size.x - 8.0:
		target.x = mouse_position.x - tooltip_size.x - OFFSET.x
	target.x = maxf(8.0, target.x)
	target.y = clampf(target.y, 8.0, maxf(8.0, viewport_size.y - tooltip_size.y - 8.0))
	global_position = target


func _equipment_column(item: Dictionary, caption: String, header: String, equipped_items: Array) -> VBoxContainer:
	var column := VBoxContainer.new()
	column.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
	column.add_theme_constant_override("separation", 7)
	if not caption.is_empty():
		column.add_child(ItemTooltip.label(caption, 12, M3.PRIMARY, HORIZONTAL_ALIGNMENT_CENTER))
	ItemTooltip.fill_equipment(column, item, equipped_items, header)
	return column


func _add_hint(hint: String) -> void:
	if hint.is_empty():
		return
	_content.add_child(ItemTooltip.label(hint, 12, M3.ON_SURFACE_VARIANT))


func _clear() -> void:
	for child in _content.get_children():
		_content.remove_child(child)
		child.queue_free()


func _finish() -> void:
	_ignore_mouse(_content)
	reset_size()
	visible = true
	_refit()


## Wrapped labels only know their height once laid out at their real width, so
## shrink again after the layout pass.
func _refit() -> void:
	await get_tree().process_frame
	if not visible:
		return
	reset_size()
	follow(_mouse_position)


static func _ignore_mouse(node: Node) -> void:
	if node is Control:
		node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for child in node.get_children():
		_ignore_mouse(child)
