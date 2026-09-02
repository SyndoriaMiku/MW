from rest_framework import serializers
from django.utils import timezone

from .models import Party, PartyMember, PartyInvitation, PendingPartyLoot


class PartyMemberSerializer(serializers.ModelSerializer):
    character_id = serializers.CharField(source='character.id', read_only=True)
    character_name = serializers.CharField(source='character.name', read_only=True)
    character_level = serializers.IntegerField(source='character.level', read_only=True)
    is_leader = serializers.SerializerMethodField()

    class Meta:
        model = PartyMember
        fields = ['character_id', 'character_name', 'character_level', 'position', 'joined_at', 'is_leader']

    def get_is_leader(self, obj):
        return obj.party.leader_id == obj.character_id


class PartySerializer(serializers.ModelSerializer):
    leader_id = serializers.CharField(source='leader.id', read_only=True)
    leader_name = serializers.CharField(source='leader.name', read_only=True)
    members = PartyMemberSerializer(source='party_members', many=True, read_only=True)
    member_count = serializers.SerializerMethodField()
    pending_loot_count = serializers.SerializerMethodField()

    class Meta:
        model = Party
        fields = [
            'id', 'name', 'leader_id', 'leader_name',
            'max_size', 'member_count', 'members',
            'pending_loot_count', 'created_at'
        ]

    def get_member_count(self, obj):
        # Hits prefetch cache if prefetch_related was called
        return obj.party_members.count()

    def get_pending_loot_count(self, obj):
        return obj.pending_loots.count()


class PartyInvitationSerializer(serializers.ModelSerializer):
    party_id = serializers.CharField(source='party.id', read_only=True)
    party_name = serializers.CharField(source='party.name', read_only=True)
    sender_name = serializers.CharField(source='sender.name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.name', read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = PartyInvitation
        fields = [
            'id', 'party_id', 'party_name',
            'sender_name', 'receiver_name',
            'status', 'created_at', 'expires_at', 'is_expired'
        ]

    def get_is_expired(self, obj):
        return timezone.now() > obj.expires_at


class PendingPartyLootSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item_template.name', read_only=True)
    item_type = serializers.CharField(source='item_template.item_type', read_only=True)

    class Meta:
        model = PendingPartyLoot
        fields = ['id', 'item_name', 'item_type', 'quantity', 'dropped_at']
