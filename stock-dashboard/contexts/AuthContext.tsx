'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User, authApi, LoginData, RegisterData } from '../lib/api';

// Types
interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginData) => Promise<void>;
  register: (userData: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  checkUsername: (username: string) => Promise<{ available: boolean; message: string }>;
}

interface AuthProviderProps {
  children: ReactNode;
}

// Create Context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Custom hook to use AuthContext
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// AuthProvider Component
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // 인증 상태 새로고침
  const refreshAuth = async () => {
    try {
      setIsLoading(true);
      const authStatus = await authApi.getStatus();
      
      if (authStatus.authenticated && authStatus.user) {
        setUser(authStatus.user);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Failed to refresh auth status:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  // 로그인
  const login = async (credentials: LoginData) => {
    try {
      setIsLoading(true);
      const response = await authApi.login(credentials);
      
      setUser(response.user);
      setIsAuthenticated(true);
      
      // 성공 메시지 표시 (선택사항)
      console.log('로그인 성공:', response.message);
    } catch (error) {
      console.error('Login failed:', error);
      throw error; // 컴포넌트에서 에러 처리할 수 있도록
    } finally {
      setIsLoading(false);
    }
  };

  // 회원가입
  const register = async (userData: RegisterData) => {
    try {
      setIsLoading(true);
      const response = await authApi.register(userData);
      // 백엔드가 이메일 인증이 필수인 경우 자동 로그인 없이 안내만 반환할 수 있음
      
      setUser(response.user);
      setIsAuthenticated(true);
      
      console.log('회원가입 성공:', response.message);
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // 로그아웃
  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout API failed:', error);
      // 로그아웃은 API 실패해도 로컬 상태는 초기화
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      
      // 로그아웃 이벤트 발생 (다른 컴포넌트들이 감지할 수 있도록)
      window.dispatchEvent(new CustomEvent('logout'));
      localStorage.setItem('logout-event', Date.now().toString());
      localStorage.removeItem('logout-event'); // 즉시 제거 (이벤트 트리거용)
    }
  };

  // 사용자명 중복 확인
  const checkUsername = async (username: string) => {
    return await authApi.checkUsername(username);
  };

  // 컴포넌트 마운트 시 인증 상태 확인
  useEffect(() => {
    refreshAuth();
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    refreshAuth,
    checkUsername,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthProvider; 