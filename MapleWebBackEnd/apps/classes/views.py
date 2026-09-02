from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import CharacterClass, Job
from .serializers import CharacterClassSerializer, JobSerializer

class CharacterClassViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CharacterClass.objects.all()
    serializer_class = CharacterClassSerializer
    permission_classes = [AllowAny]

class JobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
