'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Loader2, Eye, EyeOff, TrendingUp, Check, X } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { RegisterData, handleApiError } from '@/lib/api';

interface FormErrors {
  [key: string]: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const { register, checkUsername, isAuthenticated, isLoading } = useAuth();
  
  const [formData, setFormData] = useState<RegisterData>({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
  });
  
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState(0);
  const [usernameStatus, setUsernameStatus] = useState<'idle' | 'checking' | 'available' | 'taken'>('idle');
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  // 이미 로그인된 경우 대시보드로 리다이렉트
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  // 비밀번호 강도 계산
  const calculatePasswordStrength = useCallback((password: string): number => {
    let score = 0;
    
    if (password.length >= 8) score += 25;
    if (password.length >= 12) score += 25;
    if (/[a-z]/.test(password)) score += 10;
    if (/[A-Z]/.test(password)) score += 10;
    if (/[0-9]/.test(password)) score += 15;
    if (/[^A-Za-z0-9]/.test(password)) score += 15;
    
    return Math.min(score, 100);
  }, []);

  // 아이디 중복 확인
  const checkUsernameAvailability = useCallback(
    async (username: string) => {
      if (username.length < 3) return;
      
      setUsernameStatus('checking');
      try {
        const result = await checkUsername(username);
        setUsernameStatus(result.available ? 'available' : 'taken');
        
        if (!result.available) {
          setErrors(prev => ({
            ...prev,
            username: result.message
          }));
        } else {
          setErrors(prev => {
            const newErrors = { ...prev };
            delete newErrors.username;
            return newErrors;
          });
        }
      } catch (error) {
        setUsernameStatus('idle');
      }
    },
    [checkUsername]
  );

  // 디바운스된 아이디 체크
  useEffect(() => {
    if (formData.username.length >= 3) {
      const timer = setTimeout(() => {
        checkUsernameAvailability(formData.username);
      }, 500);
      return () => clearTimeout(timer);
    } else {
      setUsernameStatus('idle');
    }
  }, [formData.username, checkUsernameAvailability]);

  // 비밀번호 강도 업데이트
  useEffect(() => {
    setPasswordStrength(calculatePasswordStrength(formData.password));
  }, [formData.password, calculatePasswordStrength]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    // 입력 시 해당 필드 에러 제거
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // 아이디 검증
    if (!formData.username.trim()) {
      newErrors.username = '아이디를 입력해주세요.';
    } else if (formData.username.length < 3) {
      newErrors.username = '아이디는 3자 이상이어야 합니다.';
    } else if (usernameStatus === 'taken') {
      newErrors.username = '이미 사용 중인 아이디입니다.';
    }

    // 이메일 검증
    if (!formData.email.trim()) {
      newErrors.email = '이메일을 입력해주세요.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = '올바른 이메일 형식을 입력해주세요.';
    }

    // 비밀번호 검증
    if (!formData.password) {
      newErrors.password = '비밀번호를 입력해주세요.';
    } else if (formData.password.length < 8) {
      newErrors.password = '비밀번호는 8자 이상이어야 합니다.';
    }

    // 비밀번호 확인 검증
    if (!formData.password_confirm) {
      newErrors.password_confirm = '비밀번호 확인을 입력해주세요.';
    } else if (formData.password !== formData.password_confirm) {
      newErrors.password_confirm = '비밀번호가 일치하지 않습니다.';
    }

    // 약관 동의 검증
    if (!agreedToTerms) {
      newErrors.terms = '서비스 약관에 동의해주세요.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setIsSubmitting(true);
    setErrors({});

    try {
      await register(formData);
      // 이메일 인증이 필요한 환경에서는 안내 메시지를 표시하고 로그인으로 유도
      router.push('/');
    } catch (error) {
      const errorMessage = handleApiError(error);
      setErrors({ general: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  // 로딩 중이면 로딩 스피너 표시
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  const getPasswordStrengthText = () => {
    if (passwordStrength < 30) return '약함';
    if (passwordStrength < 60) return '보통';
    if (passwordStrength < 80) return '강함';
    return '매우 강함';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-gray-100 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <TrendingUp className="h-8 w-8 text-blue-600 mr-2" />
            <h1 className="text-2xl font-bold text-gray-900">KOSPI Dashboard</h1>
          </div>
          <p className="text-gray-600">새 계정을 만들어 시작하세요</p>
        </div>

        {/* 회원가입 카드 */}
        <Card className="shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">회원가입</CardTitle>
            <CardDescription className="text-center">
              무료 계정을 만들어 모든 기능을 이용하세요
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* 일반 에러 메시지 */}
              {errors.general && (
                <Alert variant="destructive">
                  <AlertDescription>{errors.general}</AlertDescription>
                </Alert>
              )}

              {/* 이름 필드들 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name">이름</Label>
                  <Input
                    id="first_name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleInputChange}
                    placeholder="이름"
                    disabled={isSubmitting}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name">성</Label>
                  <Input
                    id="last_name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleInputChange}
                    placeholder="성"
                    disabled={isSubmitting}
                  />
                </div>
              </div>

              {/* 아이디 입력 */}
              <div className="space-y-2">
                <Label htmlFor="username">아이디 *</Label>
                <div className="relative">
                  <Input
                    id="username"
                    name="username"
                    value={formData.username}
                    onChange={handleInputChange}
                    placeholder="아이디 (3자 이상)"
                    className={errors.username ? 'border-red-500 pr-10' : usernameStatus === 'available' ? 'border-green-500 pr-10' : 'pr-10'}
                    disabled={isSubmitting}
                  />
                  <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                    {usernameStatus === 'checking' && <Loader2 className="h-4 w-4 animate-spin text-gray-500" />}
                    {usernameStatus === 'available' && <Check className="h-4 w-4 text-green-500" />}
                    {usernameStatus === 'taken' && <X className="h-4 w-4 text-red-500" />}
                  </div>
                </div>
                {errors.username && (
                  <p className="text-sm text-red-500">{errors.username}</p>
                )}
                {usernameStatus === 'available' && !errors.username && (
                  <p className="text-sm text-green-600">사용 가능한 아이디입니다.</p>
                )}
              </div>

              {/* 이메일 입력 */}
              <div className="space-y-2">
                <Label htmlFor="email">이메일 *</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  placeholder="이메일을 입력하세요"
                  className={errors.email ? 'border-red-500' : ''}
                  disabled={isSubmitting}
                />
                {errors.email && (
                  <p className="text-sm text-red-500">{errors.email}</p>
                )}
              </div>

              {/* 비밀번호 입력 */}
              <div className="space-y-2">
                <Label htmlFor="password">비밀번호 *</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder="비밀번호 (8자 이상)"
                    className={errors.password ? 'border-red-500 pr-10' : 'pr-10'}
                    disabled={isSubmitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
                    disabled={isSubmitting}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                
                {/* 비밀번호 강도 표시 */}
                {formData.password && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">비밀번호 강도</span>
                      <span className={`font-medium ${passwordStrength < 60 ? 'text-red-500' : 'text-green-600'}`}>
                        {getPasswordStrengthText()}
                      </span>
                    </div>
                    <Progress 
                      value={passwordStrength} 
                      className="h-2"
                    />
                  </div>
                )}
                
                {errors.password && (
                  <p className="text-sm text-red-500">{errors.password}</p>
                )}
              </div>

              {/* 비밀번호 확인 */}
              <div className="space-y-2">
                <Label htmlFor="password_confirm">비밀번호 확인 *</Label>
                <div className="relative">
                  <Input
                    id="password_confirm"
                    name="password_confirm"
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={formData.password_confirm}
                    onChange={handleInputChange}
                    placeholder="비밀번호를 다시 입력하세요"
                    className={errors.password_confirm ? 'border-red-500 pr-10' : 'pr-10'}
                    disabled={isSubmitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
                    disabled={isSubmitting}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password_confirm && (
                  <p className="text-sm text-red-500">{errors.password_confirm}</p>
                )}
              </div>

              {/* 약관 동의 */}
              <div className="space-y-4">
                <div className="flex items-start space-x-2">
                  <input
                    id="terms"
                    type="checkbox"
                    checked={agreedToTerms}
                    onChange={(e) => setAgreedToTerms(e.target.checked)}
                    className="mt-1 rounded border-gray-300"
                    disabled={isSubmitting}
                  />
                  <Label htmlFor="terms" className="text-sm leading-5">
                    서비스 약관과 개인정보 처리방침에 동의합니다. *
                  </Label>
                </div>
                {errors.terms && (
                  <p className="text-sm text-red-500">{errors.terms}</p>
                )}
              </div>

              {/* 회원가입 버튼 */}
              <Button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700"
                disabled={isSubmitting || usernameStatus === 'checking'}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    계정 생성 중...
                  </>
                ) : (
                  '계정 만들기'
                )}
              </Button>

              {/* 로그인 링크 */}
              <div className="text-center">
                <div className="text-sm text-gray-600">
                  이미 계정이 있으신가요?{' '}
                  <Link
                    href="/login"
                    className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                  >
                    로그인
                  </Link>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* 푸터 */}
        <div className="text-center mt-8 text-sm text-gray-500">
          © 2024 KOSPI Dashboard. All rights reserved.
        </div>
      </div>
    </div>
  );
} 