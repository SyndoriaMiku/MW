from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Character
from .serializers import CharacterSerializer, CharacterSkillSerializer

class MyCharacterView(viewsets.ViewSet):
    """
    ViewSet for managing the user's character.
    """
    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        POST /
        Create a character for the current user.
        """
        if getattr(request.user, 'character', None) is not None:
            return Response(
                {"detail": "User already has a character."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CharacterSerializer(data=request.data)
        if serializer.is_valid():
            character = serializer.save()
            request.user.character = character
            request.user.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my(self, request):
        """
        GET /my/
        Retrieve the current user's character.
        """
        if getattr(request.user, 'character', None) is not None:
            serializer = CharacterSerializer(request.user.character)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "User has no character."},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=False, methods=['get'])
    def skills(self, request):
        """Return skills owned by the authenticated user's character."""
        character = getattr(request.user, 'character', None)
        if character is None:
            return Response(
                {"detail": "User has no character."},
                status=status.HTTP_404_NOT_FOUND,
            )
        skills = character.skills.select_related('skill_template').all()
        return Response(CharacterSkillSerializer(skills, many=True).data)
