from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password as django_validate_password
from .models import User

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )

    def validate_password(self, value):
        django_validate_password(value)
        return value

    def validate_email(self, value):
        return User.objects.normalize_email(value)
