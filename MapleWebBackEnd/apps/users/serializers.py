from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import NovaTransaction

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'password')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    # The model's username format validator runs too; the DB constraints back these up.
    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value

    def validate(self, attrs):
        # Run AUTH_PASSWORD_VALIDATORS, including similarity to the username/email.
        candidate = User(username=attrs.get('username'), email=attrs.get('email'))
        try:
            validate_password(attrs.get('password'), user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class PasswordChangeSerializer(serializers.Serializer):
    """Checks the new password; the view checks the old one against the login limits."""
    old_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value, user=self.context['request'].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value


class PublicUserSerializer(serializers.ModelSerializer):
    """What other players may see about an account: no email or balances."""
    character_id = serializers.PrimaryKeyRelatedField(
        read_only=True,
        source='character'
    )

    class Meta:
        model = User
        fields = ('id', 'username', 'character_id')
        read_only_fields = fields


class NovaTransactionSerializer(serializers.ModelSerializer):
    """A player's own Nova history; the admin note and author stay internal."""

    class Meta:
        model = NovaTransaction
        fields = ('id', 'kind', 'amount', 'balance_after', 'description', 'created_at')
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    character_id = serializers.PrimaryKeyRelatedField(
        read_only=True, 
        source='character'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'lumis', 'nova', 'character_id')
        read_only_fields = ('username', 'email', 'lumis', 'nova')
