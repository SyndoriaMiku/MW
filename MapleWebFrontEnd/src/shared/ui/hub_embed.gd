class_name HubEmbed
extends RefCounted

## Screens that also run as hub pages. The hub marks them with the meta
## "embedded"; they then hide their standalone chrome (back button) and use the
## content box's padding.

const PAGE_MARGIN := 20


static func is_embedded(screen: Node) -> bool:
	return screen.has_meta("embedded")


static func adapt(screen: Control, hidden: Array, margin: MarginContainer) -> void:
	if not is_embedded(screen):
		return
	for node in hidden:
		node.visible = false
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, PAGE_MARGIN)
