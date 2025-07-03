'use client';

import { useState, useEffect, useCallback } from 'react';
import { realTimeClient, RealTimePriceData } from '@/lib/websocket-client';

interface StockPriceDisplay extends RealTimePriceData {
  name?: string;
  last_updated: string;
}

export default function RealTimePage() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMessage, setConnectionMessage] = useState('');
  const [stockPrices, setStockPrices] = useState<Map<string, StockPriceDisplay>>(new Map());
  const [subscribedStocks, setSubscribedStocks] = useState<string[]>([]);
  const [newStockCode, setNewStockCode] = useState('');

  // 주요 종목 정보
  const stockNames: { [key: string]: string } = {
    '005930': '삼성전자',
    '000660': 'SK하이닉스',
    '035420': 'NAVER',
    '005490': 'POSCO홀딩스',
    '051910': 'LG화학',
    '006400': '삼성SDI',
    '035720': '카카오',
    '012330': '현대모비스',
    '028260': '삼성물산',
    '207940': '삼성바이오로직스'
  };

  // 가격 업데이트 콜백
  const handlePriceUpdate = useCallback((data: RealTimePriceData) => {
    setStockPrices(prev => {
      const newMap = new Map(prev);
      newMap.set(data.stock_code, {
        ...data,
        name: stockNames[data.stock_code] || data.stock_code,
        last_updated: new Date().toLocaleTimeString()
      });
      return newMap;
    });
  }, []);

  // 연결 상태 콜백
  const handleConnectionChange = useCallback((connected: boolean, message?: string) => {
    setIsConnected(connected);
    setConnectionMessage(message || '');
  }, []);

  useEffect(() => {
    // WebSocket 연결 및 콜백 등록
    const initializeWebSocket = async () => {
      console.log('🚀 Initializing WebSocket connection...');
      
      realTimeClient.onConnectionChange(handleConnectionChange);
      
      try {
        console.log('🔌 Attempting to connect to WebSocket...');
        const connected = await realTimeClient.connect();
        
        if (connected) {
          console.log('✅ WebSocket connected successfully');
          
          // 주요 종목들 자동 구독
          const majorStocks = Object.keys(stockNames).slice(0, 5);
          console.log('📊 Subscribing to stocks:', majorStocks);
          
          realTimeClient.subscribe(majorStocks, handlePriceUpdate);
          setSubscribedStocks(majorStocks);
        } else {
          console.error('❌ Failed to connect to WebSocket');
          setConnectionMessage('WebSocket 연결에 실패했습니다. 서버를 확인해주세요.');
        }
      } catch (error) {
        console.error('🔥 WebSocket initialization error:', error);
        setConnectionMessage(`연결 오류: ${error}`);
      }
    };

    initializeWebSocket();

    // 컴포넌트 언마운트 시 연결 해제
    return () => {
      console.log('🔌 Disconnecting WebSocket...');
      realTimeClient.disconnect();
    };
  }, [handlePriceUpdate, handleConnectionChange]);

  // 새 종목 구독
  const handleSubscribe = () => {
    if (newStockCode && !subscribedStocks.includes(newStockCode)) {
      realTimeClient.subscribe([newStockCode], handlePriceUpdate);
      setSubscribedStocks(prev => [...prev, newStockCode]);
      setNewStockCode('');
    }
  };

  // 종목 구독 해제
  const handleUnsubscribe = (stockCode: string) => {
    realTimeClient.unsubscribe([stockCode]);
    setSubscribedStocks(prev => prev.filter(code => code !== stockCode));
    setStockPrices(prev => {
      const newMap = new Map(prev);
      newMap.delete(stockCode);
      return newMap;
    });
  };

  // 가격 변동 색상 결정
  const getPriceColor = (changeAmount: number) => {
    if (changeAmount > 0) return 'text-red-600';
    if (changeAmount < 0) return 'text-blue-600';
    return 'text-gray-600';
  };

  // 변동률 포맷팅
  const formatChangePercent = (percent: number) => {
    const sign = percent > 0 ? '+' : '';
    return `${sign}${percent.toFixed(2)}%`;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          📊 실시간 주가 대시보드
        </h1>
        
        {/* 연결 상태 표시 */}
        <div className="flex items-center space-x-4 mb-6">
          <div className={`flex items-center space-x-2 px-3 py-2 rounded-lg ${
            isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            <div className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}></div>
            <span className="font-medium">
              {isConnected ? '🟢 연결됨' : '🔴 연결 끊김'}
            </span>
          </div>
          {connectionMessage && (
            <span className="text-sm text-gray-600">{connectionMessage}</span>
          )}
        </div>

        {/* 새 종목 추가 */}
        <div className="flex space-x-2 mb-6">
          <input
            type="text"
            value={newStockCode}
            onChange={(e) => setNewStockCode(e.target.value)}
            placeholder="종목코드 입력 (예: 005930)"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            maxLength={6}
          />
          <button
            onClick={handleSubscribe}
            disabled={!isConnected || !newStockCode}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            구독 추가
          </button>
        </div>
      </div>

      {/* 실시간 주가 테이블 */}
      <div className="bg-white rounded-lg shadow-lg overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b">
          <h2 className="text-xl font-semibold text-gray-900">
            실시간 주가 정보 ({stockPrices.size}개 종목)
          </h2>
        </div>
        
        {stockPrices.size === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            구독 중인 종목이 없습니다. 위에서 종목을 추가해주세요.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    종목
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    현재가
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    전일대비
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    등락률
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    거래량
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    업데이트
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    액션
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {Array.from(stockPrices.values()).map((stock) => (
                  <tr key={stock.stock_code} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {stock.name}
                        </div>
                        <div className="text-sm text-gray-500">
                          {stock.stock_code}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                      {stock.current_price.toLocaleString()}원
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-right text-sm font-medium ${getPriceColor(stock.change_amount)}`}>
                      {stock.change_amount > 0 ? '+' : ''}{stock.change_amount.toLocaleString()}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-right text-sm font-medium ${getPriceColor(stock.change_amount)}`}>
                      {formatChangePercent(stock.change_percent)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                      {stock.volume.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {stock.last_updated}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <button
                        onClick={() => handleUnsubscribe(stock.stock_code)}
                        className="text-red-600 hover:text-red-900 text-sm"
                      >
                        구독해제
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 통계 정보 */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-medium text-gray-900 mb-2">연결 상태</h3>
          <p className="text-2xl font-bold text-blue-600">
            {isConnected ? '온라인' : '오프라인'}
          </p>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-medium text-gray-900 mb-2">구독 종목 수</h3>
          <p className="text-2xl font-bold text-green-600">
            {subscribedStocks.length}개
          </p>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-medium text-gray-900 mb-2">실시간 업데이트</h3>
          <p className="text-2xl font-bold text-purple-600">
            {stockPrices.size}개
          </p>
        </div>
      </div>

      {/* 도움말 */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-medium text-blue-900 mb-2">💡 사용 방법</h3>
        <ul className="list-disc list-inside text-sm text-blue-800 space-y-1">
          <li>페이지 로드 시 주요 종목들이 자동으로 구독됩니다</li>
          <li>상단 입력창에 6자리 종목코드를 입력하여 새 종목을 추가할 수 있습니다</li>
          <li>실시간으로 주가가 업데이트되며, 상승은 빨간색, 하락은 파란색으로 표시됩니다</li>
          <li>각 종목의 '구독해제' 버튼을 클릭하여 실시간 업데이트를 중단할 수 있습니다</li>
          <li>연결이 끊어져도 자동으로 재연결을 시도합니다</li>
        </ul>
      </div>
    </div>
  );
} 