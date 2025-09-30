from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
from . import services


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')
    
    def validate_username(self, value):
        value = (value or '').strip()
        # 중복 체크는 대소문자 구분 없이 수행
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('이미 사용 중인 아이디입니다.')
        return value
    
    def validate_email(self, value):
        value = (value or '').strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('이미 사용 중인 이메일입니다.')
        return value
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError('비밀번호가 일치하지 않습니다.')
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # 입력값 정규화
            username = (username or '').strip()
            request = self.context.get('request') if hasattr(self, 'context') else None
            client_ip = services.get_client_ip(request) if request is not None else ''

            # Lockout check
            if services.is_locked(username, client_ip):
                raise serializers.ValidationError('로그인 시도가 잠시 제한되었습니다. 잠시 후 다시 시도해주세요.')

            user = authenticate(username=username, password=password)
            if not user:
                attempts = services.record_failed_attempt(username, client_ip)
                max_attempts = int(getattr(settings, 'AUTH_MAX_LOGIN_ATTEMPTS', 5))
                if attempts >= max_attempts:
                    services.lock_account(username, client_ip)
                raise serializers.ValidationError('아이디 또는 비밀번호가 올바르지 않습니다.')
            # Success: reset counters
            services.reset_attempts(username, client_ip)
            attrs['user'] = user
        else:
            raise serializers.ValidationError('아이디와 비밀번호를 모두 입력해주세요.')
        
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined')
        read_only_fields = ('id', 'username', 'date_joined') 