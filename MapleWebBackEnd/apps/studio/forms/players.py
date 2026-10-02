from django import forms

from apps.users.models import NovaTransaction

from ..fields import StudioForm


class ReasonForm(StudioForm):
    reason = forms.CharField(label='Lý do (ghi vào lịch sử)', max_length=200, required=False)


class NovaChangeForm(StudioForm):
    """A Nova ledger entry: donations add, adjustments add or take away."""
    kind = forms.ChoiceField(label='Loại', choices=[
        (NovaTransaction.Kind.DONATION, 'Donate (cộng Nova)'),
        (NovaTransaction.Kind.ADJUSTMENT, 'Điều chỉnh (cộng hoặc trừ)'),
    ])
    amount = forms.IntegerField(label='Số Nova', help_text='Số dương để cộng, số âm để trừ (chỉ với điều chỉnh).')
    reference = forms.CharField(label='Mã donate', max_length=100, required=False,
                                help_text='Mỗi mã chỉ cộng được một lần, ví dụ mã giao dịch Ko-fi.')
    description = forms.CharField(label='Nội dung người chơi thấy', max_length=200, required=False)
    note = forms.CharField(label='Ghi chú nội bộ', required=False, widget=forms.Textarea(attrs={'rows': 2}))
