from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


class StaffRequiredMixin:
    """Studio pages are for staff; others log in through the Django admin login page."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('admin:login'))
        if not (user.is_active and user.is_staff):
            raise PermissionDenied('Studio is for staff accounts.')
        return super().dispatch(request, *args, **kwargs)
