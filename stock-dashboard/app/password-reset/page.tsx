'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import { Loader2, ArrowLeft, TrendingUp, Mail, CheckCircle } from 'lucide-react';
import { authApi, handleApiError } from '@/lib/api';

export default function PasswordResetPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [tempPassword, setTempPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email.trim()) {
      setError('이메일을 입력해주세요.');
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('올바른 이메일 형식을 입력해주세요.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const response = await authApi.requestPasswordReset(email);
      setMessage(response.message);
      setTempPassword(response.temp_password || '');
      setSuccess(true);
    } catch (error) {
      const errorMessage = handleApiError(error);
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-gray-100 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* 헤더 */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center mb-4">
              <TrendingUp className="h-8 w-8 text-blue-600 mr-2" />
              <h1 className="text-2xl font-bold text-gray-900">KOSPI Dashboard</h1>
            </div>
          </div>

          {/* 성공 카드 */}
          <Card className="shadow-lg">
            <CardHeader className="text-center">
              <div className="flex justify-center mb-4">
                <CheckCircle className="h-16 w-16 text-green-500" />
              </div>
              <CardTitle className="text-2xl font-bold text-green-600">
                이메일 발송 완료
              </CardTitle>
              <CardDescription>
                비밀번호 재설정 안내가 발송되었습니다
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert>
                <Mail className="h-4 w-4" />
                <AlertDescription>
                  {message}
                </AlertDescription>
              </Alert>

              {tempPassword && (
                <Alert>
                  <AlertDescription>
                    <strong>개발 모드 임시 비밀번호:</strong> {tempPassword}
                    <br />
                    <small className="text-gray-500">
                      이 비밀번호로 로그인 후 새 비밀번호로 변경하세요.
                    </small>
                  </AlertDescription>
                </Alert>
              )}

              <div className="space-y-3 pt-4">
                <Button
                  onClick={() => router.push('/login')}
                  className="w-full bg-blue-600 hover:bg-blue-700"
                >
                  로그인 페이지로 이동
                </Button>
                <Button
                  variant="outline"
                  onClick={() => router.push('/password-reset/confirm')}
                  className="w-full"
                >
                  새 비밀번호 설정
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-gray-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <TrendingUp className="h-8 w-8 text-blue-600 mr-2" />
            <h1 className="text-2xl font-bold text-gray-900">KOSPI Dashboard</h1>
          </div>
          <p className="text-gray-600">비밀번호를 재설정하세요</p>
        </div>

        {/* 비밀번호 재설정 카드 */}
        <Card className="shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">
              비밀번호 재설정
            </CardTitle>
            <CardDescription className="text-center">
              등록된 이메일 주소를 입력하면 비밀번호 재설정 링크를 발송해드립니다
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* 에러 메시지 */}
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* 이메일 입력 */}
              <div className="space-y-2">
                <Label htmlFor="email">이메일 주소</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@email.com"
                  className={error ? 'border-red-500' : ''}
                  disabled={isSubmitting}
                />
              </div>

              {/* 재설정 요청 버튼 */}
              <Button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    발송 중...
                  </>
                ) : (
                  <>
                    <Mail className="mr-2 h-4 w-4" />
                    비밀번호 재설정 링크 발송
                  </>
                )}
              </Button>

              {/* 뒤로가기 링크 */}
              <div className="text-center">
                <Link 
                  href="/login" 
                  className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
                >
                  <ArrowLeft className="mr-1 h-4 w-4" />
                  로그인 페이지로 돌아가기
                </Link>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 