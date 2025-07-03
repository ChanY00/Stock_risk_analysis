'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function WebSocketTest() {
  const [status, setStatus] = useState('DISCONNECTED');
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const addMessage = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages(prev => [...prev, `[${timestamp}] ${message}`]);
  };

  const connectWebSocket = () => {
    if (typeof window === 'undefined') {
      addMessage('❌ Server-side execution detected');
      return;
    }

    if (typeof WebSocket === 'undefined') {
      addMessage('❌ WebSocket not supported');
      setError('WebSocket not supported by this browser');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      addMessage('⚠️ Already connected');
      return;
    }

    const wsUrl = 'ws://localhost:8000/ws/stocks/realtime/';
    addMessage(`🔌 Connecting to ${wsUrl}...`);
    setStatus('CONNECTING');
    setError(null);

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = (event) => {
        setStatus('CONNECTED');
        addMessage('✅ WebSocket connected successfully!');
        console.log('WebSocket opened:', event);
      };

      wsRef.current.onmessage = (event) => {
        addMessage(`📥 Received: ${event.data}`);
        try {
          const data = JSON.parse(event.data);
          console.log('Parsed message:', data);
        } catch (e) {
          console.log('Raw message:', event.data);
        }
      };

      wsRef.current.onclose = (event) => {
        setStatus('DISCONNECTED');
        addMessage(`🔌 Connection closed: code=${event.code}, reason="${event.reason}"`);
        console.log('WebSocket closed:', event);
      };

      wsRef.current.onerror = (event) => {
        setStatus('ERROR');
        const errorMsg = `WebSocket error: ${JSON.stringify(event)}`;
        addMessage(`❌ ${errorMsg}`);
        setError(errorMsg);
        console.error('WebSocket error:', event);
        
        // 상세 디버깅 정보
        if (wsRef.current) {
          console.log('WebSocket state:', wsRef.current.readyState);
          console.log('WebSocket URL:', wsRef.current.url);
        }
      };

    } catch (error) {
      const errorMsg = `Failed to create WebSocket: ${error}`;
      addMessage(`❌ ${errorMsg}`);
      setError(errorMsg);
      setStatus('ERROR');
      console.error('WebSocket creation error:', error);
    }
  };

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close(1000, 'User requested disconnect');
      wsRef.current = null;
      setStatus('DISCONNECTED');
      addMessage('🔌 Disconnected by user');
    }
  };

  const sendTestMessage = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const testMessage = {
        action: 'subscribe',
        stock_codes: ['005930']
      };
      wsRef.current.send(JSON.stringify(testMessage));
      addMessage(`📤 Sent: ${JSON.stringify(testMessage)}`);
    } else {
      addMessage('❌ WebSocket is not connected');
    }
  };

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, []);

  const getStatusColor = () => {
    switch (status) {
      case 'CONNECTED': return 'text-green-600';
      case 'CONNECTING': return 'text-yellow-600';
      case 'ERROR': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>🔌 WebSocket 연결 테스트</CardTitle>
        <CardDescription>
          실시간 주가 WebSocket 연결 상태를 테스트합니다
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span>상태:</span>
            <span className={`font-bold ${getStatusColor()}`}>
              {status}
            </span>
          </div>
          <div className="space-x-2">
            <Button 
              onClick={connectWebSocket} 
              disabled={status === 'CONNECTED'}
              variant="default"
              size="sm"
            >
              연결
            </Button>
            <Button 
              onClick={disconnectWebSocket}
              disabled={status !== 'CONNECTED'}
              variant="outline"
              size="sm"
            >
              해제
            </Button>
            <Button 
              onClick={sendTestMessage}
              disabled={status !== 'CONNECTED'}
              variant="secondary"
              size="sm"
            >
              테스트 메시지
            </Button>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="border rounded p-3 h-64 overflow-y-auto bg-gray-50">
          <div className="text-sm font-mono space-y-1">
            {messages.length === 0 ? (
              <div className="text-gray-500">메시지가 없습니다...</div>
            ) : (
              messages.map((msg, index) => (
                <div key={index} className="text-xs">
                  {msg}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="text-xs text-gray-500 space-y-1">
          <div><strong>환경:</strong> {typeof window !== 'undefined' ? 'Client' : 'Server'}</div>
          <div><strong>WebSocket 지원:</strong> {typeof WebSocket !== 'undefined' ? '✅' : '❌'}</div>
          <div><strong>URL:</strong> ws://localhost:8000/ws/stocks/realtime/</div>
        </div>
      </CardContent>
    </Card>
  );
} 