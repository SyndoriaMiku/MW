from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.inventory.models import InventoryItem


class Command(BaseCommand):
    help = (
        "Delete inventory items whose time limit has passed. Expired items are "
        "already out of play; run this periodically (e.g. hourly) to remove them."
    )

    def handle(self, *args, **options):
        expired = InventoryItem.objects.filter(expired_at__lte=timezone.now())
        count = expired.count()
        # Equipped slots, Aurora lines and pending rolls cascade with the items.
        expired.delete()
        self.stdout.write(f"Deleted {count} expired items.")
