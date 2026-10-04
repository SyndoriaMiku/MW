class_name IconTexture
extends RefCounted

## Material Symbols glyphs rasterized to textures, for places that take a
## Texture2D (Button.icon, TextureRect). Cached per icon, color and size.

static var _cache: Dictionary = {}


static func make(icon_name: String, color: Color, pixel_size: int = 24) -> Texture2D:
	var key := "%s|%s|%d" % [icon_name, color.to_html(), pixel_size]
	if _cache.has(key):
		return _cache[key]
	var texture := ImageTexture.create_from_image(_render(icon_name, color, pixel_size))
	_cache[key] = texture
	return texture


static func _render(icon_name: String, color: Color, pixel_size: int) -> Image:
	var canvas := Image.create(pixel_size, pixel_size, false, Image.FORMAT_RGBA8)
	canvas.fill(Color.TRANSPARENT)
	var font: FontFile = M3.ICON_FONT
	var size := Vector2i(pixel_size, 0)
	var glyph := font.get_glyph_index(pixel_size, int(M3.ICONS.get(icon_name, 0)), 0)
	if glyph == 0:
		return canvas
	font.render_glyph(0, size, glyph)
	var texture_index := font.get_glyph_texture_idx(0, size, glyph)
	if texture_index < 0:
		return canvas
	var atlas := font.get_texture_image(0, size, texture_index)
	var uv := font.get_glyph_uv_rect(0, size, glyph)
	var region := Rect2i(uv.position, uv.size)
	if atlas == null or region.size.x <= 0 or region.size.y <= 0:
		return canvas
	var bitmap := atlas.get_region(region)
	bitmap.convert(Image.FORMAT_LA8)
	var origin := (Vector2i(pixel_size, pixel_size) - region.size) / 2
	for y in region.size.y:
		for x in region.size.x:
			var alpha := bitmap.get_pixel(x, y).a
			var target := origin + Vector2i(x, y)
			if alpha > 0.0 and target.x >= 0 and target.y >= 0 and target.x < pixel_size and target.y < pixel_size:
				canvas.set_pixelv(target, Color(color.r, color.g, color.b, color.a * alpha))
	return canvas
