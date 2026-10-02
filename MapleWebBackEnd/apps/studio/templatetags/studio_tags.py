from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if hasattr(mapping, 'get') else None


@register.filter
def show(value):
    """A history value as people read it: lists joined, yes/no for booleans, a dash for nothing."""
    if value is None or value == '' or value == []:
        return '—'
    if isinstance(value, bool):
        return 'Có' if value else 'Không'
    if isinstance(value, (list, tuple)):
        return ', '.join(str(show(item)) for item in value)
    if isinstance(value, dict):
        return ', '.join(f'{key}: {show(item)}' for key, item in value.items())
    return value
