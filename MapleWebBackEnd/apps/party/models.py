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
    members = models.ManyToManyField('characters.Character', related_name='parties')

    max_size = models.PositiveIntegerField(default=4)
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
        unique_together = ('party', 'character')
        unique_together = ('party', 'position')
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

    def save(self, *args, **kwargs):
        # Set expiration time to 24 hours from creation if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=5) # For testing, set to 5 minutes
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation from {self.sender.name} to {self.receiver.name} for Party {self.party.name} - Status: {self.status}"
    

