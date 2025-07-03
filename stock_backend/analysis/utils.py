import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from stocks.models import StockPrice

class TechnicalAnalysis:
    """기술적 지표 계산을 위한 클래스"""
    
    @staticmethod
    def get_price_data(stock, days=252):
        """주가 데이터를 pandas DataFrame으로 가져오기"""
        prices = stock.prices.order_by('-date')[:days][::-1]  # 최신순으로 가져와서 역순으로
        
        if not prices:
            return None
            
        data = []
        for price in prices:
            data.append({
                'date': price.date,
                'open': price.open_price,
                'high': price.high_price,
                'low': price.low_price,
                'close': price.close_price,
                'volume': price.volume
            })
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df
    
    @staticmethod
    def calculate_moving_averages(df: pd.DataFrame) -> dict:
        """이동평균 계산 (5일, 20일, 60일)"""
        if df is None or len(df) < 60:
            return {'ma5': None, 'ma20': None, 'ma60': None}
        
        ma5 = df['close'].rolling(window=5).mean().iloc[-1] if len(df) >= 5 else None
        ma20 = df['close'].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else None
        ma60 = df['close'].rolling(window=60).mean().iloc[-1] if len(df) >= 60 else None
        
        return {
            'ma5': float(ma5) if pd.notna(ma5) else None,
            'ma20': float(ma20) if pd.notna(ma20) else None,
            'ma60': float(ma60) if pd.notna(ma60) else None
        }
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period=14) -> Optional[float]:
        """RSI (Relative Strength Index) 계산"""
        if df is None or len(df) < period + 1:
            return None
        
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> dict:
        """MACD 계산"""
        if df is None or len(df) < slow + signal:
            return {'macd': None, 'macd_signal': None, 'macd_histogram': None}
        
        exp1 = df['close'].ewm(span=fast).mean()
        exp2 = df['close'].ewm(span=slow).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else None,
            'macd_signal': float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else None,
            'macd_histogram': float(histogram.iloc[-1]) if pd.notna(histogram.iloc[-1]) else None
        }
    
    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period=20, std_dev=2) -> dict:
        """볼린저 밴드 계산"""
        if df is None or len(df) < period:
            return {'bollinger_upper': None, 'bollinger_middle': None, 'bollinger_lower': None}
        
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return {
            'bollinger_upper': float(upper_band.iloc[-1]) if pd.notna(upper_band.iloc[-1]) else None,
            'bollinger_middle': float(sma.iloc[-1]) if pd.notna(sma.iloc[-1]) else None,
            'bollinger_lower': float(lower_band.iloc[-1]) if pd.notna(lower_band.iloc[-1]) else None
        }
    
    @staticmethod
    def calculate_stochastic(df: pd.DataFrame, k_period=14, d_period=3) -> dict:
        """스토캐스틱 오실레이터 계산"""
        if df is None or len(df) < k_period:
            return {'stochastic_k': None, 'stochastic_d': None}
        
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        
        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'stochastic_k': float(k_percent.iloc[-1]) if pd.notna(k_percent.iloc[-1]) else None,
            'stochastic_d': float(d_percent.iloc[-1]) if pd.notna(d_percent.iloc[-1]) else None
        }
    
    @classmethod
    def calculate_all_indicators(cls, stock) -> dict:
        """모든 기술적 지표를 한번에 계산"""
        df = cls.get_price_data(stock)
        
        if df is None:
            return {}
        
        indicators = {}
        
        # 이동평균
        indicators.update(cls.calculate_moving_averages(df))
        
        # RSI
        indicators['rsi'] = cls.calculate_rsi(df)
        
        # MACD
        indicators.update(cls.calculate_macd(df))
        
        # 볼린저 밴드
        indicators.update(cls.calculate_bollinger_bands(df))
        
        # 스토캐스틱
        indicators.update(cls.calculate_stochastic(df))
        
        return indicators 