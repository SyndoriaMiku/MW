class_name StaminaClock
extends RefCounted

## Client-side stamina regeneration, mirroring Character.update_stamina on the
## backend: one point every REGEN_SECONDS since last_stamina_update, up to the
## maximum. Times are Unix seconds on the server's clock.

const REGEN_SECONDS := 180

var current := 0
var maximum := 0
var last_update := 0.0


static func from_character(character: Dictionary) -> StaminaClock:
	var clock := StaminaClock.new()
	clock.current = int(character.get("current_stamina", 0))
	clock.maximum = int(character.get("max_stamina", 0))
	clock.last_update = iso_to_unix(str(character.get("last_stamina_update", "")))
	return clock


## Stamina at `now`, counting the points regenerated since the last update.
func value_at(now: float) -> int:
	if current >= maximum or last_update <= 0.0:
		return current
	var regenerated := int(floor(maxf(0.0, now - last_update) / REGEN_SECONDS))
	return mini(maximum, current + regenerated)


## Seconds until the next point, 0 when full.
func seconds_to_next(now: float) -> int:
	if value_at(now) >= maximum or last_update <= 0.0:
		return 0
	var elapsed := maxf(0.0, now - last_update)
	return int(ceil(REGEN_SECONDS - fmod(elapsed, REGEN_SECONDS)))


## Seconds until stamina is full, 0 when full.
func seconds_to_full(now: float) -> int:
	var missing := maximum - value_at(now)
	if missing <= 0:
		return 0
	return seconds_to_next(now) + (missing - 1) * REGEN_SECONDS


## "1:05" under an hour, "3h 05m" above.
static func duration_text(seconds: int) -> String:
	if seconds >= 3600:
		return "%dh %02dm" % [seconds / 3600, (seconds % 3600) / 60]
	return "%d:%02d" % [seconds / 60, seconds % 60]


## Parses a DRF timestamp ("2026-10-03T08:15:30.123456Z" or with "+07:00").
## Returns 0 when it cannot be read.
static func iso_to_unix(text: String) -> float:
	var value := text.strip_edges()
	if value.length() < 19:
		return 0.0
	var offset_seconds := 0
	var zone := ""
	if value.ends_with("Z"):
		value = value.left(-1)
	else:
		var sign_at := maxi(value.rfind("+"), value.rfind("-"))
		if sign_at > 10:
			zone = value.substr(sign_at)
			value = value.left(sign_at)
	if not zone.is_empty():
		var parts := zone.substr(1).split(":")
		offset_seconds = int(parts[0]) * 3600 + (int(parts[1]) * 60 if parts.size() > 1 else 0)
		if zone.begins_with("-"):
			offset_seconds = -offset_seconds
	var fraction := 0.0
	var dot := value.find(".")
	if dot != -1:
		fraction = float("0" + value.substr(dot))
		value = value.left(dot)
	var unix := Time.get_unix_time_from_datetime_string(value)
	return float(unix) + fraction - offset_seconds
