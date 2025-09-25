from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from django.contrib.auth import authenticate
from .serializers import UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny, IsAuthenticated

# Create your views here.


class RegisterView (APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"userMsg": "Đăng ký thành công"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class LoginView (APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status.HTTP_200_OK)
        return Response({"userMsg": "Đăng nhập thất bại"}, status=status.HTTP_401_UNAUTHORIZED)
    
class UserDetailView (APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user #Get the user object
        if not user:
            return Response({"userMsg": "Không tìm thấy người dùng"}, status=status.HTTP_404_NOT_FOUND)
        
        data = {
            "username": user.username,
            "email": user.email,
            "lumis": user.lumis,
            "character": user.character.name if user.character else None
        }
        return Response(data, status=status.HTTP_200_OK)
    
    def put(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"userMsg": "Cập nhật thành công"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request):
        user = request.user
        user.delete()
        return Response({"userMsg": "Xóa tài khoản thành công"}, status=status.HTTP_204_NO_CONTENT)