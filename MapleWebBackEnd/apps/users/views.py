from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.settings import api_settings
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from . import login_limits
from .models import NovaTransaction
from .serializers import NovaTransactionSerializer, UserRegistrationSerializer, UserProfileSerializer

User = get_user_model()

class LoginView(TokenObtainPairView):
    """JWT login that locks an account or IP after too many wrong passwords."""

    def post(self, request, *args, **kwargs):
        username = request.data.get('username') if hasattr(request.data, 'get') else None
        username = username if isinstance(username, str) else ''
        ip = BaseThrottle().get_ident(request)

        wait = login_limits.seconds_locked(username, ip)
        if wait:
            return Response(
                {"detail": f"Too many failed login attempts. Try again in {wait} seconds."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(wait)},
            )

        try:
            response = super().post(request, *args, **kwargs)
        except (AuthenticationFailed, InvalidToken):
            # simplejwt raises on wrong credentials; dispatch turns it into a 401.
            login_limits.record_failure(username, ip)
            raise
        if response.status_code == status.HTTP_200_OK:
            login_limits.record_success(username)
        return response


class RegisterThrottle(SimpleRateThrottle):
    """Sign-up attempts per IP, successful or not (rate: DEFAULT_THROTTLE_RATES['register'])."""
    scope = 'register'

    def get_rate(self):
        # SimpleRateThrottle copies the rates at import; read them per request instead.
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    throttle_classes = (RegisterThrottle,)
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError:
            # Another request took the username or email after validation.
            username = request.data.get('username', '')
            if User.objects.filter(username__iexact=username).exists():
                errors = {"username": ["This username is already taken."]}
            else:
                errors = {"email": ["This email is already registered."]}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

class NovaHistoryView(generics.ListAPIView):
    """GET: the caller's Nova transactions (donations, purchases, adjustments), newest first."""
    permission_classes = (IsAuthenticated,)
    serializer_class = NovaTransactionSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return NovaTransaction.objects.none()
        return NovaTransaction.objects.filter(user=self.request.user).order_by('-created_at', '-id')


class ProfileView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class SessionBootstrapView(APIView):
    """Return the minimum authenticated state needed to initialize a game client."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        from apps.battles.serializers import CombatInstanceSerializer
        from apps.battles.services import BattleService
        from apps.characters.models import RateEvent
        from apps.characters.serializers import CharacterSerializer, RateEventSerializer
        from apps.party.models import PartyMember
        from apps.party.serializers import PartySerializer

        character = getattr(request.user, 'character', None)
        party = None
        active_battle = None

        if character is not None:
            membership = PartyMember.objects.filter(character=character).select_related('party').first()
            if membership:
                party = membership.party
            active_battle = BattleService.get_active_combat_for_character(character)

        return Response({
            "server_time": timezone.now(),
            "api_version": "1.0",
            "battle_turn_timeout_seconds": settings.BATTLE_TURN_TIMEOUT_SECONDS,
            "profile": UserProfileSerializer(request.user).data,
            "character": CharacterSerializer(character).data if character else None,
            "party": PartySerializer(party).data if party else None,
            "active_battle": CombatInstanceSerializer(active_battle).data if active_battle else None,
            "rate_events": RateEventSerializer(RateEvent.objects.running(), many=True).data,
            "feature_flags": {
                "battle_events": True,
                "stable_combatant_targets": True,
                "effect_tick_events": True,
                "action_idempotency": True,
                "trade_cancel": True,
                "battle_forfeit": True,
                "battle_items": True,
                "realtime_battle": False,
            },
        })
