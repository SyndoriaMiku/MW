from datetime import timedelta

from django.db import models
from django.conf import settings
from apps.characters.models import generate_hex_id
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

class Party(models.Model):
    """
    Save active party information
    """
    id = models.CharField(primary_key=True, max_length=8, default=generate_hex_id, editable=False)
    name = models.CharField(max_length=100)

    # Members of the party
    leader = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='led_parties')

    max_size = models.PositiveIntegerField(default=4)
    # Auto-created to run a normal dungeon alone. The player silently leaves it
    # when creating or joining a real party; the row keeps the battle history.
    is_solo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Party {self.name} (Leader: {self.leader.name})"

class PartyMember(models.Model):
    """
    Party member model to track members in a party
    """
    party = models.ForeignKey('party.Party', on_delete=models.CASCADE, related_name='party_members')
    character = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='party_memberships')
    
    position = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)]) #Position in party (1-4)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('party', 'character'), ('party', 'position'))
        constraints = [
            # A character belongs to at most one party at a time.
            models.UniqueConstraint(fields=['character'], name='one_party_per_character'),
        ]
        ordering = ['party', 'position']
    def __str__(self):
        return f"{self.character.name} in Party {self.party.name} at position {self.position}"
    
class PartyInvitation(models.Model):
    """
    Invitation to join a party
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        EXPIRED = 'expired', 'Expired'

    party = models.ForeignKey('party.Party', on_delete=models.CASCADE, related_name='invitations')

    sender = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='sent_invitations')
    receiver = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='received_invitations')

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField() #Invitation expires at

    TTL = timedelta(hours=1)

    def save(self, *args, **kwargs):
        # Invitations expire an hour after they are sent unless set explicitly
        if not self.expires_at:
            self.expires_at = timezone.now() + self.TTL
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation from {self.sender.name} to {self.receiver.name} for Party {self.party.name} - Status: {self.status}"

class PendingPartyLoot(models.Model):
    """
    Stores shared loot dropped for the party during combat.
    The Party Leader can distribute these items to party members.
    """
    party = models.ForeignKey('party.Party', on_delete=models.CASCADE, related_name='pending_loots')
    item_template = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    dropped_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Pending Party Loot"
        verbose_name_plural = "Pending Party Loots"
        ordering = ['-dropped_at']

    def __str__(self):
        return f"{self.quantity}x {self.item_template.name} (Party {self.party.name})"
