class_name ItemTooltip
extends RefCounted

## Builds the rich item description used by hover tooltips (character profile
## and inventory): Lumen, set effects, stat boosts split by source, and Aurora.

const STAT_DEFINITIONS := [
	["str", "STR"], ["agi", "AGI"], ["int", "INT"],
	["att", "ATT"], ["hp", "HP"], ["mp", "MP"],
	["all_stats", "ALL STATS"],
]
const UP_COLOR := Color("79dfa3")
const DOWN_COLOR := Color("ff8a80")


## Fills `box` with an equipment description; `header` is shown next to the
## icon (e.g. "CURRENTLY EQUIPPED"). `equipped_items` count set pieces.
static func fill_equipment(box: VBoxContainer, item: Dictionary, equipped_items: Array, header: String) -> void:
	var template: Dictionary = item.get("template", {})
	_add_lumen_summary(box, item)
	box.add_child(label(str(template.get("name", "Unknown Item")), 20, Color("f5f7fb"), HORIZONTAL_ALIGNMENT_CENTER))
	var trade_text := "Untradeable" if bool(item.get("is_untrade", false)) or not bool(template.get("is_tradeable", true)) else "Tradeable"
	box.add_child(label(trade_text, 13, Color("e49a55"), HORIZONTAL_ALIGNMENT_CENTER))
	box.add_child(HSeparator.new())

	var overview := HBoxContainer.new()
	overview.add_theme_constant_override("separation", 14)
	box.add_child(overview)
	overview.add_child(_icon_panel(template, 104))
	var summary := VBoxContainer.new()
	summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	summary.alignment = BoxContainer.ALIGNMENT_CENTER
	summary.add_child(label(header, 17, Color("d7dee7"), HORIZONTAL_ALIGNMENT_RIGHT))
	summary.add_child(label(str(template.get("item_type", "equipment")).replace("_", " ").capitalize(), 14, Color("aebbc9"), HORIZONTAL_ALIGNMENT_RIGHT))
	summary.add_child(label("Required Level  %d" % int(template.get("minimum_level", 1)), 14, Color("eef2f6"), HORIZONTAL_ALIGNMENT_RIGHT))
	overview.add_child(summary)

	_add_set_effect_section(box, template, item, equipped_items)
	box.add_child(HSeparator.new())
	box.add_child(label("STAT BOOSTS", 13, Color("b8c2cc")))
	var stats := RichTextLabel.new()
	stats.bbcode_enabled = true
	stats.fit_content = true
	stats.scroll_active = false
	stats.custom_minimum_size = Vector2(0, 72)
	stats.text = stat_bbcode(template, item)
	box.add_child(stats)
	box.add_child(HSeparator.new())
	_add_aurora_section(box, item)


## Fills `box` with a short description for a non-equipment item.
static func fill_simple(box: VBoxContainer, item: Dictionary, hint: String) -> void:
	var template: Dictionary = item.get("template", {})
	var overview := HBoxContainer.new()
	overview.add_theme_constant_override("separation", 12)
	box.add_child(overview)
	overview.add_child(_icon_panel(template, 64))
	var summary := VBoxContainer.new()
	summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	summary.alignment = BoxContainer.ALIGNMENT_CENTER
	summary.add_child(label(str(template.get("name", "Unknown Item")), 18, Color("f5f7fb")))
	summary.add_child(label("%s  •  ×%d" % [str(template.get("item_type", "etc")).replace("_", " ").capitalize(), int(item.get("quantity", 1))], 13, Color("aebbc9")))
	overview.add_child(summary)
	var description := str(template.get("description", ""))
	box.add_child(HSeparator.new())
	box.add_child(label(description if not description.is_empty() else "No description.", 14, Color("d7dee7")))
	if not hint.is_empty():
		box.add_child(label(hint, 12, Color("66c9f5")))


## Stat totals of one item by stat key (base + Lumen + flat Aurora + other).
static func stat_totals(item: Dictionary) -> Dictionary:
	var template: Dictionary = item.get("template", {})
	var breakdown: Variant = item.get("stat_breakdown", {})
	var lumen := _lumen_stats(item)
	var aurora := _aurora_flat_stats(item)
	var other: Variant = item.get("enhancement_stat_boosts", {})
	var totals := {}
	for definition in STAT_DEFINITIONS:
		var key: String = definition[0]
		var stat_breakdown: Dictionary = breakdown.get(key, {}) if breakdown is Dictionary else {}
		if stat_breakdown.has("total"):
			totals[key] = float(stat_breakdown.total)
			continue
		var base := float(stat_breakdown.get("base", template.get("%s_boost" % key, 0)))
		var extra := float(other.get(key, 0)) if other is Dictionary else 0.0
		totals[key] = base + float(lumen.get(key, 0)) + float(aurora.get(key, 0)) + extra
	totals["drop_rate"] = float(template.get("drop_rate_boost", 0.0))
	return totals


## [[stat name, change]] for every stat that differs: `candidate` minus `current`
## (an empty `current` means the slot is empty).
static func stat_changes(candidate: Dictionary, current: Dictionary) -> Array:
	var after := stat_totals(candidate)
	var before := stat_totals(current) if not current.is_empty() else {}
	var changes: Array = []
	for definition in STAT_DEFINITIONS + [["drop_rate", "DROP RATE"]]:
		var change := float(after.get(definition[0], 0)) - float(before.get(definition[0], 0))
		if not is_zero_approx(change):
			changes.append([definition[1], change])
	return changes


static func stat_changes_bbcode(changes: Array) -> String:
	if changes.is_empty():
		return "[color=#8e9aa7]No stat change[/color]"
	var lines := PackedStringArray()
	for change in changes:
		var color := UP_COLOR if float(change[1]) > 0.0 else DOWN_COLOR
		var suffix := "%" if change[0] == "DROP RATE" else ""
		lines.append("[color=#edf2f7]%s[/color]  [color=#%s]%s%s[/color]" % [change[0], color.to_html(false), signed_number(float(change[1])), suffix])
	return "\n".join(lines)


static func stat_bbcode(template: Dictionary, item: Dictionary) -> String:
	var output := PackedStringArray()
	var breakdown: Dictionary = item.get("stat_breakdown", {})
	var lumen_stats := _lumen_stats(item)
	var future_stats: Dictionary = item.get("enhancement_stat_boosts", {})
	var aurora_flat := _aurora_flat_stats(item)
	for definition in STAT_DEFINITIONS:
		var stat_key: String = definition[0]
		var stat_name: String = definition[1]
		var base_value := float(template.get("%s_boost" % stat_key, 0))
		var stat_breakdown: Dictionary = breakdown.get(stat_key, {})
		if stat_breakdown.has("base"):
			base_value = float(stat_breakdown.get("base", base_value))
		var lumen_value := float(stat_breakdown.get("lumen", lumen_stats.get(stat_key, 0)))
		var aurora_value := float(stat_breakdown.get("aurora", aurora_flat.get(stat_key, 0)))
		var future_value := float(stat_breakdown.get("other", future_stats.get(stat_key, 0)))
		var total := float(stat_breakdown.get("total", base_value + lumen_value + aurora_value + future_value))
		if is_zero_approx(total) and is_zero_approx(base_value) and is_zero_approx(lumen_value) and is_zero_approx(aurora_value) and is_zero_approx(future_value):
			continue
		var components := PackedStringArray()
		var has_non_base_component := not is_zero_approx(lumen_value) or not is_zero_approx(aurora_value) or not is_zero_approx(future_value)
		if has_non_base_component:
			components.append("[color=#ffffff]%s[/color]" % plain_number(base_value))
		if not is_zero_approx(lumen_value):
			components.append("[color=#63d7ef]%s[/color]" % plain_number(lumen_value))
		if not is_zero_approx(aurora_value):
			components.append("[color=#c48cff]%s[/color]" % plain_number(aurora_value))
		if not is_zero_approx(future_value):
			components.append("[color=#73dda1]%s[/color]" % plain_number(future_value))
		var stat_text := "[color=#edf2f7]%s:[/color]  [color=#59c9f5]%s[/color]" % [stat_name, plain_number(total)]
		if has_non_base_component:
			stat_text += "  (%s)" % " + ".join(components)
		output.append(stat_text)
	var drop_rate := float(template.get("drop_rate_boost", 0.0))
	if not is_zero_approx(drop_rate):
		output.append("[color=#edf2f7]DROP RATE:[/color]  [color=#59c9f5]%s%%[/color]  ([color=#ffffff]%s%%[/color])" % [plain_number(drop_rate), plain_number(drop_rate)])
	if output.is_empty():
		return "[color=#8e9aa7]No direct stat boosts[/color]"
	return "\n".join(output)


static func equipped_set_piece_count(set_data: Dictionary, equipped_items: Array) -> int:
	var member_ids := {}
	var members: Variant = set_data.get("items", [])
	if members is Array:
		for member_value in members:
			if member_value is Dictionary:
				member_ids[ApiClient.id_string(member_value.get("id"))] = true
	var equipped_member_ids := {}
	for equipped in equipped_items:
		var equipped_item: Dictionary = equipped.get("item", {})
		var template_id := ApiClient.id_string(equipped_item.get("template", {}).get("id"))
		if member_ids.has(template_id):
			equipped_member_ids[template_id] = true
	return equipped_member_ids.size()


static func set_effect_stats_text(effect: Dictionary) -> String:
	var parts := PackedStringArray()
	for definition in [
		["hp_boost", "HP"], ["mp_boost", "MP"], ["att_boost", "ATT"],
		["str_boost", "STR"], ["agi_boost", "AGI"], ["int_boost", "INT"],
		["all_stats_boost", "ALL STATS"],
	]:
		var value := float(effect.get(definition[0], 0))
		if not is_zero_approx(value):
			parts.append("%s %s" % [definition[1], signed_number(value)])
	return "  •  ".join(parts) if not parts.is_empty() else "No stat bonus"


static func label(text: String, font_size: int, color: Color, alignment := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var result := Label.new()
	result.text = text
	result.horizontal_alignment = alignment
	result.add_theme_font_size_override("font_size", font_size)
	result.add_theme_color_override("font_color", color)
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return result


static func signed_number(value: float) -> String:
	if is_equal_approx(value, round(value)):
		return "%+d" % int(value)
	return "%+.1f" % value


static func plain_number(value: float) -> String:
	if is_equal_approx(value, round(value)):
		return "%d" % int(value)
	return "%.1f" % value


static func _icon_panel(template: Dictionary, size: int) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(size, size)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("56616d")
	style.border_color = Color("8a96a2")
	style.set_border_width_all(2)
	style.set_corner_radius_all(5)
	style.set_content_margin_all(7)
	panel.add_theme_stylebox_override("panel", style)
	var icon := TextureRect.new()
	icon.texture = ItemIcons.for_template(template)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	panel.add_child(icon)
	return panel


static func _add_set_effect_section(box: VBoxContainer, template: Dictionary, item: Dictionary, equipped_items: Array) -> void:
	var sets: Variant = item.get("set_effects", template.get("item_sets", []))
	if not sets is Array:
		return
	var visible_sets: Array = sets.filter(func(set_data): return set_data is Dictionary)
	if visible_sets.is_empty():
		return
	box.add_child(HSeparator.new())
	box.add_child(label("SET EFFECT", 12, Color("9ca8b4")))
	for set_data in visible_sets:
		var active_count := equipped_set_piece_count(set_data, equipped_items)
		var members: Variant = set_data.get("items", [])
		var member_count: int = members.size() if members is Array else 0
		var count_text := "  %d/%d" % [active_count, member_count] if member_count > 0 else ""
		box.add_child(label(str(set_data.get("name", "Equipment Set")) + count_text, 13, Color("e0c66d")))
		var effects: Variant = set_data.get("effects", [])
		if not effects is Array:
			continue
		for effect in effects:
			if not effect is Dictionary:
				continue
			var required_count := int(effect.get("required_count", 0))
			var is_active := active_count >= required_count
			box.add_child(label(
				"%s  %d SET  %s" % ["●" if is_active else "○", required_count, set_effect_stats_text(effect)],
				12,
				UP_COLOR if is_active else Color("7d8995")
			))


static func _lumen_stats(item: Dictionary) -> Dictionary:
	var result := {}
	var lumen_breakdown: Variant = item.get("lumen_breakdown", {})
	if not lumen_breakdown is Dictionary:
		return result
	var total: Variant = lumen_breakdown.get("total", {})
	if not total is Dictionary:
		return result
	for stat_key in ["hp", "mp", "att", "str", "agi", "int"]:
		result[stat_key] = float(total.get("%s_boost" % stat_key, 0))
	return result


static func _add_lumen_summary(box: VBoxContainer, item: Dictionary) -> void:
	var lumen_level := int(item.get("lumen_ascend_level", 0))
	if lumen_level <= 0:
		return
	var max_level := 0
	var lumen_breakdown: Variant = item.get("lumen_breakdown", {})
	if lumen_breakdown is Dictionary and lumen_breakdown.get("tier") is Dictionary:
		max_level = int(lumen_breakdown.tier.get("max_level", 0))
	var level_text := "%d/%d" % [lumen_level, max_level] if max_level > 0 else str(lumen_level)
	box.add_child(label("Lumen Ascend %s" % level_text, 14, Color("63d7ef"), HORIZONTAL_ALIGNMENT_CENTER))


static func _aurora_flat_stats(item: Dictionary) -> Dictionary:
	var result := {}
	for line in item.get("aurora_lines", []):
		if line is Dictionary and str(line.get("line_type", "flat")) == "flat":
			var stat_key := str(line.get("stat_type", ""))
			result[stat_key] = float(result.get(stat_key, 0)) + float(line.get("value", 0))
	return result


static func _add_aurora_section(box: VBoxContainer, item: Dictionary) -> void:
	box.add_child(label("AURORA  +%d" % int(item.get("aurora_level", 0)), 14, Color("c48cff")))
	var lines: Variant = item.get("aurora_lines", [])
	if not lines is Array or lines.is_empty():
		box.add_child(label("No Aurora lines", 12, Color("8e9aa7")))
		return
	for line in lines:
		if line is Dictionary:
			var suffix := "%" if str(line.get("line_type", "flat")) == "percent" else ""
			box.add_child(label("◆  %s  +%s%s" % [str(line.get("stat_type", "")).replace("_", " ").to_upper(), plain_number(float(line.get("value", 0))), suffix], 13, Color("d9a7ff")))
