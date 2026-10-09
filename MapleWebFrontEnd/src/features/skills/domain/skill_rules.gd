class_name SkillRules
extends RefCounted

## What the Skills page shows about a skill, from the backend's rules: skills
## unlock on reaching a level, an upgrade without materials happens on level-up
## by itself, and one with materials is bought with
## POST characters/my/skills/<id>/upgrade/.

const TARGET_LABELS := {
	"SELF": "Self", "ALLY": "One ally", "ENEMY": "One enemy",
	"E_AREA": "All enemies", "A_AREA": "All allies", "GLOBAL": "Everyone",
}
const EFFECT_ICONS := {
	"DAMAGE": "swords", "HEAL": "water_drop", "EFFECT": "auto_fix_high", "PASSIVE": "shield",
}


## {"kind", "text"}: kind is "max", "auto", "level", "materials" or "ready".
static func upgrade_state(skill: Dictionary, character_level: int, owned: Dictionary) -> Dictionary:
	var next: Variant = skill.get("next_upgrade")
	if not next is Dictionary:
		return {"kind": "max", "text": "Max level reached."}
	var required_level := int(next.get("required_char_level", 1))
	if not bool(next.get("requires_materials", false)):
		return {"kind": "auto", "text": "Upgrades by itself at character level %d." % required_level}
	if character_level < required_level:
		return {"kind": "level", "text": "Requires character level %d." % required_level}
	if not missing_materials(next.get("required_materials", []), owned).is_empty():
		return {"kind": "materials", "text": "Not enough materials."}
	return {"kind": "ready", "text": "Ready to upgrade."}


## Materials still missing: [{"item_template_id", "quantity", "owned"}].
static func missing_materials(required: Variant, owned: Dictionary) -> Array:
	var missing: Array = []
	if not required is Array:
		return missing
	for material in required:
		if not material is Dictionary:
			continue
		var template_id := ApiClient.id_string(material.get("item_template_id"))
		var have := int(owned.get(template_id, 0))
		if have < int(material.get("quantity", 0)):
			missing.append({"item_template_id": template_id, "quantity": int(material.get("quantity", 0)), "owned": have})
	return missing


## Item template id -> quantity held, from inventory items.
static func owned_counts(inventory: Array) -> Dictionary:
	var counts := {}
	for item in inventory:
		if not item is Dictionary:
			continue
		var template_id := ApiClient.id_string(item.get("template", {}).get("id"))
		counts[template_id] = int(counts.get(template_id, 0)) + int(item.get("quantity", 1))
	return counts


static func icon_for(skill: Dictionary) -> String:
	if bool(skill.get("is_passive", false)):
		return "shield"
	return EFFECT_ICONS.get(str(skill.get("effect_type", "")), "auto_fix_high")


## "x1.50".
static func multiplier_text(value: Variant) -> String:
	return "x%.2f" % float(value)
