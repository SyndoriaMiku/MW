"""
Login sessions. Every JWT carries the account's session_version; a token
whose version is not the account's current one is refused, both as an
access token and at refresh. Bumping the version therefore ends every
session at once, including access tokens that have not expired yet. That
happens on any password change (GameUser.set_password) and on
end_all_sessions(). Tokens issued before versions existed count as 0.
"""
from django.contrib.auth import get_user_model
from django.db.models import F
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

SESSION_CLAIM = 'session_version'
SESSION_ENDED = 'Your session has ended. Please log in again.'


def is_current(user, token):
    return token.get(SESSION_CLAIM, 0) == user.session_version


def end_all_sessions(user):
    """Log the account out on every device."""
    type(user).objects.filter(pk=user.pk).update(session_version=F('session_version') + 1)
    user.refresh_from_db(fields=['session_version'])


class SessionRefreshToken(RefreshToken):
    """A refresh token stamped with the account's session version; its access tokens copy the stamp."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token[SESSION_CLAIM] = user.session_version
        return token


def tokens_for(user):
    refresh = SessionRefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class SessionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not is_current(user, validated_token):
            raise AuthenticationFailed(SESSION_ENDED, code='session_ended')
        return user


class LoginSerializer(TokenObtainPairSerializer):
    token_class = SessionRefreshToken


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        user = get_user_model().objects.filter(
            **{api_settings.USER_ID_FIELD: refresh.get(api_settings.USER_ID_CLAIM)}
        ).first()
        if user is None or not is_current(user, refresh):
            raise AuthenticationFailed(SESSION_ENDED, code='session_ended')
        return super().validate(attrs)
