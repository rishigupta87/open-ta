import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

interface MarketData {
  symbol: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  timestamp: string;
}

interface MarketDataFeedProps {
  symbols: string[];
  wsUrl?: string;
}

const MarketDataFeed: React.FC<MarketDataFeedProps> = ({ 
  symbols, 
  wsUrl = 'ws://localhost:8000/ws/market-data' 
}) => {
  const [marketData, setMarketData] = useState<Record<string, MarketData>>({});
  const [connectionStatus, setConnectionStatus] = useState<Record<string, string>>({});
  const websockets = useRef<Record<string, WebSocket>>({});

  useEffect(() => {
    // Connect to WebSocket for each symbol
    symbols.forEach(symbol => {
      connectToSymbol(symbol);
    });

    return () => {
      // Cleanup WebSocket connections
      Object.values(websockets.current).forEach(ws => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      });
    };
  }, [symbols]);

  const connectToSymbol = (symbol: string) => {
    const ws = new WebSocket(`${wsUrl}/${symbol}`);
    
    ws.onopen = () => {
      console.log(`Connected to ${symbol}`);
      setConnectionStatus(prev => ({ ...prev, [symbol]: 'connected' }));
      
      // Send ping to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        } else {
          clearInterval(pingInterval);
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'market_data') {
          setMarketData(prev => ({
            ...prev,
            [data.symbol]: {
              symbol: data.symbol,
              ltp: data.ltp,
              open: data.open,
              high: data.high,
              low: data.low,
              volume: data.volume,
              timestamp: data.timestamp
            }
          }));
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.log(`Disconnected from ${symbol}`);
      setConnectionStatus(prev => ({ ...prev, [symbol]: 'disconnected' }));
      
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        if (!websockets.current[symbol] || websockets.current[symbol].readyState === WebSocket.CLOSED) {
          connectToSymbol(symbol);
        }
      }, 5000);
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for ${symbol}:`, error);
      setConnectionStatus(prev => ({ ...prev, [symbol]: 'error' }));
    };

    websockets.current[symbol] = ws;
  };

  const formatPrice = (price: number) => {
    return price ? price.toFixed(2) : '0.00';
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K`;
    }
    return volume.toString();
  };

  const getPriceChangeColor = (current: number, open: number) => {
    if (current > open) return 'text-green-600';
    if (current < open) return 'text-red-600';
    return 'text-gray-600';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {symbols.map(symbol => {
        const data = marketData[symbol];
        const status = connectionStatus[symbol];
        const priceChange = data ? ((data.ltp - data.open) / data.open * 100) : 0;

        return (
          <Card key={symbol} className="relative">
            <CardHeader className="pb-2">
              <CardTitle className="flex justify-between items-center">
                <span>{symbol}</span>
                <div className={`w-3 h-3 rounded-full ${
                  status === 'connected' ? 'bg-green-500' : 
                  status === 'error' ? 'bg-red-500' : 'bg-yellow-500'
                }`} />
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data ? (
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-2xl font-bold">
                      ₹{