from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'password')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    character_id = serializers.PrimaryKeyRelatedField(
        read_only=True, 
        source='character'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'lumis', 'nova', 'character_id')
        read_only_fields = ('username', 'email', 'lumis', 'nova')
