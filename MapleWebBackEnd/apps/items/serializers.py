from rest_framework import serializers
from .models import ItemTemplate

class ItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemTemplate
        fields = '__all__'
