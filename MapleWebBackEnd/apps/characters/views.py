from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Character, CharacterSkill
from .serializers import CharacterSerializer, CharacterSkillSerializer


class MyCharacterView(viewsets.ViewSet):
    """
    ViewSet for managing the user's character.
    """
    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        POST /
        Create a character for the current user.
        """
        if getattr(request.user, 'character', None) is not None:
            return Response(
                {"detail": "User already has a character."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CharacterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            character = serializer.save()
            request.user.character = character
            request.user.save(update_fields=['character'])
            from .skill_service import SkillService
            SkillService.sync_eligible_skills(character)
            character = Character.objects.select_related(
                'character_class', 'job'
            ).prefetch_related(
                'skills__skill_template__level_configs'
            ).get(pk=character.pk)
        return Response(
            CharacterSerializer(character).data,
            status=status.HTTP_201_CREATED,
        )

    def my(self, request):
        """
        GET /my/
        Retrieve the current user's character (includes skills).
        """
        if getattr(request.user, 'character', None) is not None:
            character = Character.objects.select_related(
                'character_class', 'job'
            ).prefetch_related(
                'skills__skill_template__level_configs'
            ).get(pk=request.user.character.pk)
            serializer = CharacterSerializer(character)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "User has no character."},
            status=status.HTTP_404_NOT_FOUND
        )

    def my_skills(self, request):
        """
        GET /my/skills/
        List all skills the character currently owns with level and upgrade info.
        """
        character = getattr(request.user, 'character', None)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_404_NOT_FOUND)

        skills = CharacterSkill.objects.filter(character=character).select_related(
            'skill_template', 'skill_template__job', 'skill_template__applies_effect'
        ).prefetch_related('skill_template__level_configs')
        serializer = CharacterSkillSerializer(skills, many=True)
        return Response(serializer.data)

    def upgrade_skill(self, request, char_skill_id=None):
        """
        POST /my/skills/{char_skill_id}/upgrade/
        Manually upgrade a skill using required materials (for material-gated skill levels).
        Auto-upgraded skills (no materials) are handled on level-up automatically.
        """
        character = getattr(request.user, 'character', None)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_404_NOT_FOUND)

        from .skill_service import SkillService
        success, message = SkillService.manual_upgrade(character, char_skill_id)
        if success:
            skill = CharacterSkill.objects.select_related('skill_template').get(
                id=char_skill_id, character=character
            )
            return Response({
                "detail": message,
                "skill": CharacterSkillSerializer(skill).data,
            })
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
