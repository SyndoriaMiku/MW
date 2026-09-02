from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ItemTemplate
from .serializers import ItemTemplateSerializer
from .services import LumenService
from .aurora_service import AuroraService

class ItemTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ItemTemplate.objects.all()
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

    def post(self, request, action):
        if action == 'reveal':
            inventory_item_id = request.data.get('inventory_item_id')
            if not inventory_item_id:
                return Response({"success": False, "message": "inventory_item_id is required."})
                
            result = AuroraService.reveal_aurora(request.user, inventory_item_id)
            return Response(result)
            
        elif action == 'modify':
            target_item_id = request.data.get('target_item_id')
            modifier_item_id = request.data.get('modifier_item_id')
            use_lumis = request.data.get('use_lumis', False)
            target_line_index = request.data.get('target_line_index')
            
            if not target_item_id:
                return Response({"success": False, "message": "target_item_id is required."})
                
            result = AuroraService.apply_modifier(
                user=request.user,
                target_item_id=target_item_id,
                modifier_item_id=modifier_item_id,
                use_lumis=use_lumis,
                target_line_index=target_line_index
            )
            return Response(result)
            
        elif action == 'confirm':
            inventory_item_id = request.data.get('inventory_item_id')
            action_type = request.data.get('action')
            selected_temp_ids = request.data.get('selected_temp_ids')
            
            if not inventory_item_id or not action_type:
                return Response({"success": False, "message": "inventory_item_id and action are required."})
                
            result = AuroraService.confirm_pending_roll(
                user=request.user,
                inventory_item_id=inventory_item_id,
                action=action_type,
                selected_temp_ids=selected_temp_ids
            )
            return Response(result)
            
        return Response({"success": False, "message": "Invalid action."}, status=400)
