from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView
from .views import (
    LoginView, LogoutAllView, NovaHistoryView, PasswordChangeView, ProfileView, RegisterView,
    SessionTokenRefreshView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('nova/history/', NovaHistoryView.as_view(), name='nova-history'),
    path('login/', LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', SessionTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='token_blacklist'),  # (B-5) POST với refresh token để blacklist
    path('logout-all/', LogoutAllView.as_view(), name='logout-all'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
]
