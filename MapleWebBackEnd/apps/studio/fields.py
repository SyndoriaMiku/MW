"""Form helpers shared by every Studio editor."""
from django import forms


class PercentField(forms.FloatField):
    """
    Shows a fraction stored in the database (0.25) as a percentage (25) and
    stores what is typed back as a fraction, so every rate in Studio reads in %.
    """

    def __init__(self, *, min_value=None, max_value=None, **kwargs):
        kwargs.setdefault('widget', forms.NumberInput(attrs={'step': 'any'}))
        super().__init__(min_value=min_value, max_value=max_value, **kwargs)

    def prepare_value(self, value):
        # Stored fractions arrive as numbers; redisplayed input arrives as typed text.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            percent = round(value * 100, 6)
            return int(percent) if float(percent).is_integer() else percent
        return value

    def clean(self, value):
        percent = super().clean(value)
        return None if percent is None else round(percent / 100, 10)


class StudioFormMixin:
    """Adds the Studio CSS classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            widget.attrs['class'] = (widget.attrs.get('class', '') + ' input').strip()


class StudioModelForm(StudioFormMixin, forms.ModelForm):
    pass


class StudioForm(StudioFormMixin, forms.Form):
    pass
