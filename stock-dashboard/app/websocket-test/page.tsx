'use client';

import { WebSocketTest } from '@/components/websocket-test';

export default function WebSocketTestPage() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold text-center mb-8">
        WebSocket 연결 진단 도구
      </h1>
      <WebSocketTest />
    </div>
  );
} 