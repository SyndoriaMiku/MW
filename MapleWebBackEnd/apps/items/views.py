from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ItemTemplate
from .serializers import (
    AuroraConfirmRequestSerializer,
    AuroraModifyRequestSerializer,
    AuroraRevealRequestSerializer,
    ItemTemplateSerializer,
)
from apps.inventory.models import InventoryItem
from apps.inventory.serializers import InventoryItemSerializer
from .services import LumenService
from .aurora_service import AuroraService

class ItemTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ItemTemplate.objects.select_related(
        'lumen_tier', 'aurora_tier'
    ).prefetch_related(
        'item_sets__effects', 'item_sets__items'
    )
    serializer_class = ItemTemplateSerializer
    permission_classes = [IsAuthenticated]

class LumenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action):
        if action == 'ascend':
            inventory_item_id = request.data.get('inventory_item_id')
            if not inventory_item_id:
                return Response({"success": False, "message": "inventory_item_id is required."})
            
            result = LumenService.attempt_lumen_ascend(request.user, inventory_item_id)
            return Response(result)
            
        elif action == 'restore':
            fragment_item_id = request.data.get('fragment_item_id')
            sacrifice_item_id = request.data.get('sacrifice_item_id')
            
            if not fragment_item_id:
                return Response({"success": False, "message": "fragment_item_id is required."})
                
            result = LumenService.restore_fragment(request.user, fragment_item_id, sacrifice_item_id)
            return Response(result)
            
        return Response({"success": False, "message": "Invalid action."}, status=400)

class AuroraAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _response(result, inventory_item_id=None):
        if result.get('success') and inventory_item_id:
            item = InventoryItem.objects.filter(
                pk=inventory_item_id
            ).select_related(
                'template__lumen_tier', 'template__aurora_tier'
            ).prefetch_related(
                'aurora_lines',
                'template__lumen_tier__ascend_rules',
                'template__item_sets__effects',
                'template__item_sets__items',
            ).first()
            if item:
                result = {**result, 'item': InventoryItemSerializer(item).data}
        response_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=response_status)

    def post(self, request, action):
        if action == 'reveal':
            serializer = AuroraRevealRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            inventory_item_id = serializer.validated_data['inventory_item_id']
            result = AuroraService.reveal_aurora(request.user, inventory_item_id)
            return self._response(result, inventory_item_id)
            
        elif action == 'modify':
            serializer = AuroraModifyRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            result = AuroraService.apply_modifier(
                user=request.user,
                target_item_id=data['target_item_id'],
                modifier_item_id=data.get('modifier_item_id'),
                use_lumis=data.get('use_lumis', False),
                target_line_index=data.get('target_line_index'),
            )
            return self._response(result, data['target_item_id'])
            
        elif action == 'confirm':
            serializer = AuroraConfirmRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            result = AuroraService.confirm_pending_roll(
                user=request.user,
                inventory_item_id=data['inventory_item_id'],
                action=data['action'],
                selected_temp_ids=data.get('selected_temp_ids'),
            )
            return self._response(result, data['inventory_item_id'])
            
        return Response({"success": False, "message": "Invalid action."}, status=400)
