from rest_framework import serializers
from .models import Listing, Trade, TradeItem, Transaction
from apps.inventory.serializers import InventoryItemSerializer
from apps.users.serializers import UserProfileSerializer

class ListingSerializer(serializers.ModelSerializer):
    seller = UserProfileSerializer(read_only=True)
    item_details = InventoryItemSerializer(source='item', read_only=True)

    class Meta:
        model = Listing
        fields = ['id', 'seller', 'item', 'item_details', 'price', 'is_active', 'quantity']
        read_only_fields = ['id', 'seller', 'is_active']


class TradeItemSerializer(serializers.ModelSerializer):
    item_details = InventoryItemSerializer(source='item', read_only=True)

    class Meta:
        model = TradeItem
        fields = ['id', 'item', 'item_details', 'is_sender']
        read_only_fields = ['id', 'is_sender']


class TradeSerializer(serializers.ModelSerializer):
    sender = UserProfileSerializer(read_only=True)
    receiver = UserProfileSerializer(read_only=True)
    items = TradeItemSerializer(many=True, read_only=True)
    receiver_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Trade
        fields = [
            'id', 'sender', 'receiver', 'receiver_id', 'sender_lumis', 'receiver_lumis',
            'status', 'created_at', 'items', 'sender_ready', 'receiver_ready',
            'sender_accepted', 'receiver_accepted'
        ]
        read_only_fields = [
            'id', 'sender', 'receiver', 'status', 'created_at',
            'sender_ready', 'receiver_ready', 'sender_accepted', 'receiver_accepted'
        ]
