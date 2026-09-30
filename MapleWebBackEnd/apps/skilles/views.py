from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import SkillTemplate
from apps.request_params import parse_int
from .serializers import SkillTemplateSerializer, SkillTemplateListSerializer


class SkillTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only catalog of all skill templates.

    GET /api/skills/                    -> list all skills (lightweight)
    GET /api/skills/{id}/               -> detail with level configs + effect
    GET /api/skills/?job={job_id}       -> filter by job
    GET /api/skills/?job=null           -> global skills (no job restriction)
    GET /api/skills/learnable/          -> skills the current character will unlock, with unlock_level
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
        availability = self.request.query_params.get('availability')
        if job == 'null':
            qs = qs.filter(job__isnull=True)
        elif job:
            qs = qs.filter(job_id=parse_int(job, 'job'))
        if availability:
            qs = qs.filter(availability=availability.upper())
        return qs

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def learnable(self, request):
        """
        GET /api/skills/learnable/
        Skills of the character's job (and global ones) it does not own yet,
        soonest first, each with the character level that unlocks it. Skills
        unlock automatically on reaching that level.
        """
        character = getattr(request.user, 'character', None)
        if not character:
            return Response({'detail': 'No character found.'}, status=status.HTTP_404_NOT_FOUND)

        from django.db.models import Q
        from apps.characters.models import CharacterSkill

        ownership = Q(job__isnull=True)
        if character.job_id:
            ownership |= Q(job_id=character.job_id)
        owned_ids = CharacterSkill.objects.filter(character=character).values('skill_template_id')
        templates = SkillTemplate.objects.filter(
            ownership,
            availability__in=[SkillTemplate.Availability.PLAYER, SkillTemplate.Availability.BOTH],
        ).exclude(id__in=owned_ids).select_related('job').prefetch_related('level_configs')

        upcoming = []
        for template in templates:
            first_level = next(
                (config for config in template.level_configs.all() if config.skill_level == 1), None,
            )
            # Same gate as SkillService.sync_eligible_skills: template level and level-1 config.
            unlock_level = max(
                template.required_level,
                first_level.required_char_level if first_level else template.required_level,
            )
            upcoming.append((unlock_level, template))
        upcoming.sort(key=lambda pair: (pair[0], pair[1].name))

        data = []
        for unlock_level, template in upcoming:
            row = SkillTemplateListSerializer(template).data
            row['unlock_level'] = unlock_level
            data.append(row)
        return Response(data)
