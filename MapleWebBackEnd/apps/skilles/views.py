from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import SkillTemplate
from .serializers import SkillTemplateSerializer, SkillTemplateListSerializer


class SkillTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only catalog of all skill templates.

    GET /api/skills/                    -> list all skills (lightweight)
    GET /api/skills/{id}/               -> detail with level configs + effect
    GET /api/skills/?job={job_id}       -> filter by job
    GET /api/skills/?job=null           -> global skills (no job restriction)
    GET /api/skills/?learnable=true     -> skills the current user's character can learn
    """
    permission_classes = [AllowAny]
    queryset = SkillTemplate.objects.all().select_related('job', 'applies_effect').prefetch_related('level_configs')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SkillTemplateSerializer
        return SkillTemplateListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        job = self.request.query_params.get('job')
        if job == 'null':
            qs = qs.filter(job__isnull=True)
        elif job:
            qs = qs.filter(job_id=job)
        return qs

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def learnable(self, request):
        """
        GET /api/skills/learnable/
        Returns skills the current character can unlock at their next level-up
        (or that they are missing but already qualify for).
        """
        character = getattr(request.user, 'character', None)
        if not character:
            return Response({'detail': 'No character found.'}, status=status.HTTP_404_NOT_FOUND)

        from .models import SkillLevelConfig
        from apps.characters.models import CharacterSkill

        # All skills relevant to this character's job or global
        eligible_templates = SkillTemplate.objects.filter(
            job=character.job
        ) | SkillTemplate.objects.filter(job__isnull=True)

        # Skills already owned
        owned_ids = set(
            CharacterSkill.objects.filter(character=character)
            .values_list('skill_template_id', flat=True)
        )

        # Skills that have a level-1 config with required_char_level <= character.level
        # AND are not yet owned
        learnable = eligible_templates.filter(
            level_configs__skill_level=1,
            level_configs__required_char_level__lte=character.level,
        ).exclude(id__in=owned_ids).distinct()

        serializer = SkillTemplateListSerializer(learnable, many=True)
        return Response(serializer.data)
