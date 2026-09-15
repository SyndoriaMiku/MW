from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer, UserProfileSerializer

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer

class ProfileView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class SessionBootstrapView(generics.GenericAPIView):
    """Return the minimum authenticated state needed to initialize a game client."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        from apps.battles.models import CombatInstance, Combatant
        from apps.battles.serializers import CombatInstanceSerializer
        from apps.characters.serializers import CharacterSerializer
        from apps.party.models import PartyMember
        from apps.party.serializers import PartySerializer
        from django.contrib.contenttypes.models import ContentType

        character = getattr(request.user, 'character', None)
        party = None
        active_battle = None

        if character is not None:
            membership = PartyMember.objects.filter(character=character).select_related('party').first()
            if membership:
                party = membership.party

            content_type = ContentType.objects.get_for_model(character)
            combatant = Combatant.objects.filter(
                is_player=True,
                content_type=content_type,
                objects_id=str(character.id),
                combat_instance__status=CombatInstance.CombatStatus.IN_PROGRESS,
            ).select_related('combat_instance').order_by('-combat_instance__updated_at').first()
            if combatant:
                active_battle = combatant.combat_instance

        return Response({
            "server_time": timezone.now(),
            "api_version": "1.0",
            "profile": UserProfileSerializer(request.user).data,
            "character": CharacterSerializer(character).data if character else None,
            "party": PartySerializer(party).data if party else None,
            "active_battle": CombatInstanceSerializer(active_battle).data if active_battle else None,
            "feature_flags": {
                "battle_events": True,
                "stable_combatant_targets": True,
                "realtime_battle": False,
            },
        })
