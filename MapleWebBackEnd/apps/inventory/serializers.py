from rest_framework import serializers
from .models import InventoryItem, AuroraLine
from apps.characters.models import EquippedItem
from apps.items.serializers import ItemTemplateSerializer

class AuroraLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuroraLine
        fields = '__all__'

class InventoryItemSerializer(serializers.ModelSerializer):
    aurora_lines = AuroraLineSerializer(many=True, read_only=True)
    template = ItemTemplateSerializer(read_only=True)

    class Meta:
        model = InventoryItem
        fields = '__all__'

class EquippedItemSerializer(serializers.ModelSerializer):
    item = InventoryItemSerializer(read_only=True)
    
    class Meta:
        model = EquippedItem
        fields = '__all__'
