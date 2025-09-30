from django.shortcuts import render
import os
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from rest_framework.authentication import SessionAuthentication
from django.conf import settings
from .serializers import UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer
from .services import (
    create_password_reset_token,
    send_password_reset_email,
    create_email_verification_token,
    send_email_verification,
)


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
        # 이메일 인증 토큰 발송 (존재하는 이메일에 한해)
        if user.email:
            try:
                token = create_email_verification_token(user)
                send_email_verification(user, token)
            except Exception:
                pass
        # 이메일 인증이 필수인 경우: 자동 로그인 대신 안내만
        if getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False):
            return Response({
                'message': '회원가입이 완료되었습니다. 이메일을 확인해 주세요.',
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        login(request, user)
        # 감사 로깅: 로그인 성공
        import logging
        logging.getLogger('authentication').info(
            'auth.login_success user=%s ip=%s', user.username, request.META.get('REMOTE_ADDR', '')
        )
        return Response({
            'message': '회원가입이 완료되었습니다.',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def user_login(request):
    """사용자 로그인"""
    serializer = UserLoginSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        # Remember-me support: control session expiry based on client flag
        remember_me = False
        try:
            # support both snake_case and camelCase from clients
            body_flag = request.data.get('remember_me', request.data.get('rememberMe', False))
            remember_me = bool(body_flag) in (True,)
        except Exception:
            remember_me = False

        if remember_me:
            # default 14 days unless overridden via env
            max_age = int(os.getenv('SESSION_REMEMBER_ME_AGE', '1209600'))
            request.session.set_expiry(max_age)
        else:
            # expire on browser close
            request.session.set_expiry(0)
        return Response({
            'message': '로그인되었습니다.',
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    """사용자 로그아웃"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logout(request)
        import logging
        logging.getLogger('authentication').info(
            'auth.logout user=%s ip=%s', getattr(request.user, 'username', ''), request.META.get('REMOTE_ADDR', '')
        )
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
    username = (request.data.get('username') or '').strip()
    if not username:
        return Response({'error': '아이디를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    
    exists = User.objects.filter(username__iexact=username).exists()
    return Response({
        'available': not exists,
        'message': '이미 사용 중인 아이디입니다.' if exists else '사용 가능한 아이디입니다.'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """비밀번호 재설정 요청: 토큰 발급 후 이메일 발송 (항상 동일 메시지 반환)"""
    email = request.data.get('email')
    if not email:
        return Response({'error': '이메일을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

    # 사용자 존재 여부와 무관하게 동일 응답으로 사용자 열거 방지
    try:
        user = User.objects.get(email=email)
        token = create_password_reset_token(user)
        send_password_reset_email(user, token)
    except User.DoesNotExist:
        pass

    return Response({'message': '입력하신 이메일로 비밀번호 재설정 안내를 발송했습니다.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """비밀번호 재설정: 토큰 + 이메일 + 새 비밀번호 검증"""
    from .models import PasswordResetToken

    email = request.data.get('email')
    token_str = request.data.get('token')
    new_password = request.data.get('new_password')

    if not email or not token_str or not new_password:
        return Response({'error': '이메일, 토큰, 새 비밀번호를 모두 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # 사용자 열거 방지
        return Response({'error': '토큰이 유효하지 않거나 만료되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        prt = PasswordResetToken.objects.get(user=user, token=token_str)
    except PasswordResetToken.DoesNotExist:
        return Response({'error': '토큰이 유효하지 않거나 만료되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    if not prt.is_valid():
        return Response({'error': '토큰이 유효하지 않거나 만료되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # change password
    user.set_password(new_password)
    user.save()
    prt.mark_used()
    import logging
    logging.getLogger('authentication').info('auth.password_reset user=%s', user.username)

    return Response({'message': '비밀번호가 성공적으로 변경되었습니다.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """이메일 인증: 이메일 + 토큰 검증 후 사용자 활성화(선택)"""
    from .models import EmailVerificationToken

    email = request.data.get('email')
    token_str = request.data.get('token')
    if not email or not token_str:
        return Response({'error': '이메일과 토큰을 모두 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        evt = EmailVerificationToken.objects.get(user=user, token=token_str)
    except (User.DoesNotExist, EmailVerificationToken.DoesNotExist):
        return Response({'error': '토큰이 유효하지 않거나 만료되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    if not evt.is_valid():
        return Response({'error': '토큰이 유효하지 않거나 만료되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    evt.mark_used()
    # 정책상 필요하다면 활성화
    # user.is_active = True
    # user.save(update_fields=['is_active'])
    return Response({'message': '이메일 인증이 완료되었습니다.'})
