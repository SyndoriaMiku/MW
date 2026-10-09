class_name M3
extends RefCounted

## Material 3 light color scheme (seed #336DFF: primary is the seed itself, the
## other roles are the M3 tonal palettes of its hue), the type scale and the
## motion curve. Every UI color in the game
## comes from here: the theme (built by tools/build_theme.gd) and the few
## colors scripts set themselves.

# Color roles.
const PRIMARY := Color("336dff")
const ON_PRIMARY := Color("ffffff")
const PRIMARY_CONTAINER := Color("dbe1ff")
const ON_PRIMARY_CONTAINER := Color("00164d")
const SECONDARY := Color("595e72")
const ON_SECONDARY := Color("ffffff")
const SECONDARY_CONTAINER := Color("dde1f9")
const ON_SECONDARY_CONTAINER := Color("161b2c")
const TERTIARY := Color("745470")
const ON_TERTIARY := Color("ffffff")
const TERTIARY_CONTAINER := Color("ffd6f7")
const ON_TERTIARY_CONTAINER := Color("2b122a")
const SURFACE := Color("faf8ff")
const SURFACE_DIM := Color("dad9e0")
const SURFACE_CONTAINER_LOWEST := Color("ffffff")
const SURFACE_CONTAINER_LOW := Color("f4f3fa")
const SURFACE_CONTAINER := Color("eeedf4")
const SURFACE_CONTAINER_HIGH := Color("e9e7ef")
const SURFACE_CONTAINER_HIGHEST := Color("e3e1e9")
const ON_SURFACE := Color("1a1b21")
const ON_SURFACE_VARIANT := Color("45464f")
const OUTLINE := Color("767680")
const OUTLINE_VARIANT := Color("c6c6d0")
const INVERSE_SURFACE := Color("2f3036")
const INVERSE_ON_SURFACE := Color("f1f0f7")
const INVERSE_PRIMARY := Color("b5c4ff")
const ERROR := Color("ba1a1a")
const ON_ERROR := Color("ffffff")
const ERROR_CONTAINER := Color("ffdad6")
const ON_ERROR_CONTAINER := Color("410002")
const SCRIM := Color(0, 0, 0, 0.32)

# Extended colors for game meaning (M3 "custom colors", harmonized for a light
# surface). Text on a surface uses the plain value, fills use the container.
const SUCCESS := Color("1f6c3c")
const SUCCESS_CONTAINER := Color("b6f2c4")
const GOLD := Color("7a5900")
const GOLD_CONTAINER := Color("ffdf9e")
const EPIC := Color("7240b8")
const EPIC_CONTAINER := Color("ecdcff")
const HP := Color("2e9d5a")
const MP := Color("2f6fd6")
const EXP := Color("c99400")
const ENEMY_HP := Color("d64545")

# State layer opacities.
const HOVER_OPACITY := 0.08
const FOCUS_OPACITY := 0.10
const PRESS_OPACITY := 0.10
const DISABLED_CONTAINER_OPACITY := 0.12
const DISABLED_CONTENT_OPACITY := 0.38

# Shape (corner radii, dp).
const CORNER_EXTRA_SMALL := 4
const CORNER_SMALL := 8
const CORNER_MEDIUM := 12
const CORNER_LARGE := 16
const CORNER_CARD := 20
const CORNER_EXTRA_LARGE := 28
const CORNER_FULL := 999

# Type scale (sp).
const DISPLAY_SMALL := 36
const HEADLINE_MEDIUM := 28
const HEADLINE_SMALL := 24
const TITLE_LARGE := 22
const TITLE_MEDIUM := 16
const TITLE_SMALL := 14
const BODY_LARGE := 16
const BODY_MEDIUM := 14
const BODY_SMALL := 12
const LABEL_LARGE := 14
const LABEL_MEDIUM := 12
const LABEL_SMALL := 11

# Motion: MotionScheme.standard() — no overshoot. Durations in seconds.
const DURATION_SHORT := 0.15
const DURATION_MEDIUM := 0.3
const DURATION_LONG := 0.45

const FONT_REGULAR := preload("res://src/shared/ui/fonts/roboto_regular.tres")
const FONT_MEDIUM := preload("res://src/shared/ui/fonts/roboto_medium.tres")
const FONT_BOLD := preload("res://src/shared/ui/fonts/roboto_bold.tres")
const ICON_FONT := preload("res://assets/fonts/material-symbols-rounded.woff2")

## Material Symbols Rounded code points for the icons the game uses.
const ICONS := {
	"home": 0xe88a, "swords": 0xf889, "backpack": 0xf19c, "person": 0xe7fd,
	"auto_awesome": 0xe65f, "storefront": 0xea12, "settings": 0xe8b8,
	"logout": 0xe9ba, "bolt": 0xea0b, "refresh": 0xe5d5, "arrow_back": 0xe5c4,
	"play_arrow": 0xe037, "paid": 0xf041, "diamond": 0xead5,
	"celebration": 0xea65, "schedule": 0xe8b5, "lock": 0xe897, "castle": 0xeab1,
	"trending_up": 0xe8e5, "event": 0xe878, "account_circle": 0xe853,
	"star": 0xe838, "forest": 0xea99, "check": 0xe5ca, "close": 0xe5cd,
	"hourglass_top": 0xea5b, "military_tech": 0xea3f,
	"menu_book": 0xea19, "task_alt": 0xe2e6, "assignment": 0xe85d,
	"local_fire_department": 0xef55, "map": 0xe55b, "location_on": 0xe0c8,
	"flag": 0xe153, "redeem": 0xe8b1, "emoji_events": 0xea23, "timer": 0xe425,
	"water_drop": 0xe798, "upgrade": 0xf0fb, "groups": 0xf233,
	"check_circle": 0xe86c, "radio_button_unchecked": 0xe836,
	"arrow_forward": 0xe5c8, "lock_open": 0xe898, "shield": 0xe9e0,
	"auto_fix_high": 0xe663, "crown": 0xecb3, "stars": 0xe8d0,
}


## A color with an alpha, e.g. a state layer: M3.with_alpha(M3.ON_SURFACE, 0.08).
static func with_alpha(color: Color, alpha: float) -> Color:
	return Color(color.r, color.g, color.b, alpha)


## `base` with a state layer of `layer` at `opacity` on top (how M3 draws hover
## and pressed states on a filled container).
static func layered(base: Color, layer: Color, opacity: float) -> Color:
	return base.lerp(Color(layer.r, layer.g, layer.b, base.a), opacity)


static func icon(name: String) -> String:
	return String.chr(int(ICONS.get(name, 0x3f)))


## A Label showing a Material Symbol.
static func icon_label(name: String, size: int = 24, color: Color = ON_SURFACE_VARIANT) -> Label:
	var label := Label.new()
	label.text = icon(name)
	label.add_theme_font_override("font", ICON_FONT)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


## A flat rounded box in a color role, for scripts that build cards.
static func box(color: Color, radius: int = CORNER_MEDIUM, padding: float = 12.0, border: Color = Color.TRANSPARENT, border_width: int = 1) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(radius)
	style.set_content_margin_all(padding)
	style.corner_detail = 12
	style.anti_aliasing = true
	if border.a > 0.0:
		style.border_color = border
		style.set_border_width_all(border_width)
	return style


## Tween with the standard easing (no bounce).
static func ease_tween(tween: Tween) -> Tween:
	return tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
