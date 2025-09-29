from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from rest_framework.authentication import SessionAuthentication
from .serializers import UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """CSRF 검증을 비활성화한 세션 인증"""
    def enforce_csrf(self, request):
        return  # CSRF 검증 생략


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """사용자 회원가입"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        login(request, user)
        return Response({
            'message': '회원가입이 완료되었습니다.',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def user_login(request):
    """사용자 로그인"""
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        return Response({
            'message': '로그인되었습니다.',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class UserLogoutView(APIView):
    """사용자 로그아웃"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logout(request)
        return Response({
            'message': '로그아웃되었습니다.'
        }, status=status.HTTP_200_OK)

# 기존 함수 뷰 유지 (호환성을 위해)
user_logout = UserLogoutView.as_view()


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def profile(request):
    """사용자 프로필 조회/수정"""
    if request.method == 'GET':
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': '프로필이 업데이트되었습니다.',
                'user': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def auth_status(request):
    """인증 상태 확인"""
    if request.user.is_authenticated:
        return Response({
            'authenticated': True,
            'user': UserProfileSerializer(request.user).data
        })
    return Response({
        'authenticated': False,
        'user': None
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def check_username(request):
    """사용자명 중복 확인"""
    username = request.data.get('username')
    if not username:
        return Response({'error': '아이디를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    
    exists = User.objects.filter(username=username).exists()
    return Response({
        'available': not exists,
        'message': '이미 사용 중인 아이디입니다.' if exists else '사용 가능한 아이디입니다.'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """비밀번호 재설정 요청"""
    email = request.data.get('email')
    if not email:
        return Response({'error': '이메일을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        # 실제 구현에서는 이메일 발송 로직이 들어가야 함
        # 지금은 임시로 성공 메시지만 반환
        return Response({
            'message': f'{email}로 비밀번호 재설정 링크를 발송했습니다. (개발 모드: 임시 비밀번호는 temp123456)',
            'temp_password': 'temp123456'  # 개발용 임시 비밀번호
        })
    except User.DoesNotExist:
        return Response({
            'error': '해당 이메일로 등록된 계정을 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """비밀번호 재설정 (개발용 간단 버전)"""
    email = request.data.get('email')
    new_password = request.data.get('new_password')
    
    if not email or not new_password:
        return Response({
            'error': '이메일과 새 비밀번호를 모두 입력해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        return Response({
            'message': '비밀번호가 성공적으로 변경되었습니다.'
        })
    except User.DoesNotExist:
        return Response({
            'error': '해당 이메일로 등록된 계정을 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)
