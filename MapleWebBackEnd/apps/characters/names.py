"""
Character name rules, modelled on MapleStory: letters and digits only (no
spaces, symbols or emoji), measured in "bytes" where Latin letters and
digits count 1 and Korean, Chinese and Japanese characters count 2.

Latin means the English and Vietnamese alphabets only, so look-alike letters
(Cyrillic "е", IPA "ɑ", full-width "Ａ", ...) cannot copy another player's name.
Names are compared by name_key(): composed accents, case folded.
"""
import string
import unicodedata

from django.core.exceptions import ValidationError

MIN_WIDTH = 4
MAX_WIDTH = 12


def _vietnamese_letters():
    tones = ('', '̀', '́', '̉', '̃', '̣')
    lower = {unicodedata.normalize('NFC', base + tone) for base in 'aăâeêioôơuưy' for tone in tones}
    lower.add('đ')
    return lower | {letter.upper() for letter in lower}


NARROW_CHARACTERS = frozenset(string.ascii_letters + string.digits) | frozenset(_vietnamese_letters())
# Whole syllables and characters only: no loose Korean letters or half-width kana.
WIDE_NAME_PREFIXES = ('HANGUL SYLLABLE ', 'CJK UNIFIED IDEOGRAPH-', 'HIRAGANA LETTER ', 'KATAKANA LETTER ')
WIDE_CHARACTERS = frozenset('ー')  # Japanese long vowel mark, as in ルーキー

RULE_MESSAGE = (
    f'Character names are {MIN_WIDTH}-{MAX_WIDTH} bytes of letters and digits, with no spaces or symbols. '
    'English and Vietnamese letters and digits count 1 byte; Korean, Chinese and Japanese characters count 2.'
)


def normalize(name):
    """Trim and compose accents, so 'e' + combining marks is stored as one letter."""
    return unicodedata.normalize('NFC', name.strip())


def name_key(name):
    """What two names must not share: 'ĐứcAnh' and 'đứcanh' are the same name."""
    return normalize(name).casefold()


def character_width(character):
    """1 or 2 bytes for an allowed character, None for anything else."""
    if character in NARROW_CHARACTERS:
        return 1
    if character in WIDE_CHARACTERS or unicodedata.name(character, '').startswith(WIDE_NAME_PREFIXES):
        return 2
    return None


def validate_character_name(name):
    widths = [character_width(character) for character in normalize(name)]
    if None in widths or not MIN_WIDTH <= sum(widths) <= MAX_WIDTH:
        raise ValidationError(RULE_MESSAGE, code='invalid_character_name')
