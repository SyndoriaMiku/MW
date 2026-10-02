from django.conf import settings
from django.db import models


class StudioChange(models.Model):
    """
    One change made through Studio: who, when, what, and each field's old and
    new value. Written by apps/studio/history.py; never edited afterwards.
    """
    class Action(models.TextChoices):
        CREATE = 'create', 'Tạo mới'
        UPDATE = 'update', 'Sửa'
        DELETE = 'delete', 'Xóa'
        ACTION = 'action', 'Thao tác'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    username = models.CharField(max_length=255, help_text='Kept when the account is deleted')
    action = models.CharField(max_length=10, choices=Action.choices)
    target_type = models.CharField(max_length=100, db_index=True, help_text='Model label, e.g. items.ItemTemplate')
    target_id = models.CharField(max_length=64, blank=True, db_index=True)
    target_repr = models.CharField(max_length=255)
    summary = models.CharField(max_length=255, blank=True)
    # {field label: [old, new]}; inline rows under "_rows": {table: {added, changed, deleted}}.
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Studio change'
        verbose_name_plural = 'Studio changes'

    def __str__(self):
        return f'{self.username} {self.get_action_display()} {self.target_repr}'
