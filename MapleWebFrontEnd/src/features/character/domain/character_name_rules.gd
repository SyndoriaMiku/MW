class_name CharacterNameRules
extends RefCounted

## Client copy of the backend's character name rules
## (MapleWebBackEnd/apps/characters/names.py), so the player sees mistakes before
## submitting. The server stays authoritative.
##
## Letters and digits only, 4-12 "bytes": English and Vietnamese letters and
## digits count 1, Korean syllables, CJK ideographs and Japanese kana count 2.

const MIN_WIDTH := 4
const MAX_WIDTH := 12
const RULE_MESSAGE := "4-12 bytes of letters and digits, no spaces or symbols. Korean, Chinese and Japanese characters count 2 bytes."

## Precomposed Vietnamese letters, generated from names.py.
const VIETNAMESE_LETTERS := "ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ"

## Code point ranges of 2-byte characters, generated from names.py
## (Unicode 15.0: Hangul syllables, CJK unified ideographs, hiragana and
## katakana letters, and the long vowel mark ー).
const WIDE_RANGES := [
	[0x3041, 0x3096], [0x30A1, 0x30FA], [0x30FC, 0x30FC], [0x31F0, 0x31FF],
	[0x3400, 0x4DBF], [0x4E00, 0x9FFF], [0xAC00, 0xD7A3], [0x1AFF0, 0x1AFF3],
	[0x1AFF5, 0x1AFFB], [0x1AFFD, 0x1AFFE], [0x1B000, 0x1B001], [0x1B11F, 0x1B122],
	[0x1B132, 0x1B132], [0x1B150, 0x1B152], [0x1B155, 0x1B155], [0x1B164, 0x1B167],
	[0x20000, 0x2A6DF], [0x2A700, 0x2B739], [0x2B740, 0x2B81D], [0x2B820, 0x2CEA1],
	[0x2CEB0, 0x2EBE0], [0x30000, 0x3134A], [0x31350, 0x323AF],
]


## Total width in bytes, or -1 when the name contains a character that is not allowed.
static func width(name: String) -> int:
	var total := 0
	for character in name.strip_edges():
		var character_width := _character_width(character)
		if character_width < 0:
			return -1
		total += character_width
	return total


## Empty when the name is valid, otherwise the message to show.
static func validate(name: String) -> String:
	var name_width := width(name)
	if name_width < 0:
		return "Only letters and digits are allowed — no spaces or symbols."
	if name_width < MIN_WIDTH:
		return "Too short: at least %d bytes." % MIN_WIDTH
	if name_width > MAX_WIDTH:
		return "Too long: at most %d bytes." % MAX_WIDTH
	return ""


static func _character_width(character: String) -> int:
	var code := character.unicode_at(0)
	var is_ascii_letter := (code >= 0x41 and code <= 0x5A) or (code >= 0x61 and code <= 0x7A)
	var is_digit := code >= 0x30 and code <= 0x39
	if is_ascii_letter or is_digit or VIETNAMESE_LETTERS.contains(character):
		return 1
	for range_pair in WIDE_RANGES:
		if code >= range_pair[0] and code <= range_pair[1]:
			return 2
	return -1
