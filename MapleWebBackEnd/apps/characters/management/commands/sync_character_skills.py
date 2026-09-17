from django.core.management.base import BaseCommand, CommandError

from apps.characters.models import Character
from apps.characters.skill_service import SkillService


class Command(BaseCommand):
    help = 'Idempotently catch existing characters up to eligible automatic skill levels.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--character-id',
            dest='character_id',
            help='Sync only one character ID. Omit to sync every character.',
        )

    def handle(self, *args, **options):
        characters = Character.objects.select_related('job').order_by('pk')
        character_id = options.get('character_id')
        if character_id:
            characters = characters.filter(pk=character_id)
            if not characters.exists():
                raise CommandError(f'Character {character_id} does not exist.')

        changed = 0
        processed = 0
        for character in characters.iterator():
            processed += 1
            changed += len(SkillService.sync_eligible_skills(character))

        self.stdout.write(self.style.SUCCESS(
            f'Synced {processed} character(s); applied {changed} skill milestone(s).'
        ))
