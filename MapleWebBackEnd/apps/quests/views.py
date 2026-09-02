from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CharacterQuest
from .serializers import CharacterQuestSerializer
from .services import QuestService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quest_list(request):
    """
    Get all quests for the current character.
    Triggers lazy provisioning of daily/weekly quests.
    """
    user = request.user
    if not user.character:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)
    
    character = user.character
    
    # This triggers lazy provisioning and resets
    quests = QuestService.get_active_quests(character)
    
    # Optionally filter by type
    quest_type = request.query_params.get('type')  # daily, weekly, once
    if quest_type:
        quests = quests.filter(quest__quest_type=quest_type)
    
    # Optionally filter by status
    quest_status = request.query_params.get('status')  # in_progress, completed, claimed
    if quest_status:
        quests = quests.filter(status=quest_status)
    
    serializer = CharacterQuestSerializer(quests, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_quest_reward(request, quest_id):
    """
    Claim rewards for a completed quest.
    """
    user = request.user
    if not user.character:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)
    
    character = user.character
    result = QuestService.claim_reward(character, quest_id)
    
    if not result['success']:
        return Response({"detail": result['message']}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(result)
