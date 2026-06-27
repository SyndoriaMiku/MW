from django import forms
from .models import LumenAscendRule, AuroraLinePool, TYPE_CHOICES

class LumenAscendRuleForm(forms.ModelForm):
    item_types = forms.MultipleChoiceField(
        choices=[c for c in TYPE_CHOICES if c[0] not in ['use', 'etc']],
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more item types for this rule."
    )

    class Meta:
        model = LumenAscendRule
        fields = '__all__'

    def clean_item_types(self):
        # MultipleChoiceField returns a list of strings, which is perfect for JSONField
        return self.cleaned_data['item_types']

class AuroraLinePoolForm(forms.ModelForm):
    item_types = forms.MultipleChoiceField(
        choices=[c for c in TYPE_CHOICES if c[0] not in ['consume', 'etc']],
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more item types for this pool."
    )

    class Meta:
        model = AuroraLinePool
        fields = '__all__'

    def clean_item_types(self):
        return self.cleaned_data['item_types']
