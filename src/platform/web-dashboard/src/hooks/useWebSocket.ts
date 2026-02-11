import { useState, useEffect, useRef, useCallback } from 'react';
import { wsManager } from '@/services/websocket';

/**
 * Subscribe to a WebSocket channel with automatic REST fallback when disconnected.
 */
export function useWsChannel<T>(
  channel: string,
  fallbackFetcher?: () => Promise<T>,
  fallbackIntervalMs?: number,
): { data: T | null; connected: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [connected, setConnected] = useState(wsManager.isConnected());
  const fallbackTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Track connection state
  useEffect(() => {
    return wsManager.onConnectionChange(setConnected);
  }, []);

  // Subscribe to WS channel
  useEffect(() => {
    const unsub = wsManager.subscribe(channel, (channelData: T) => {
      setData(channelData);
    });
    return unsub;
  }, [channel]);

  // Fallback polling when disconnected
  useEffect(() => {
    if (connected || !fallbackFetcher || !fallbackIntervalMs) {
      if (fallbackTimer.current) {
        clearInterval(fallbackTimer.current);
        fallbackTimer.current = null;
      }
      return;
    }

    // Fetch immediately on disconnect
    fallbackFetcher().then(setData).catch(() => {});

    fallbackTimer.current = setInterval(() => {
      fallbackFetcher().then(setData).catch(() => {});
    }, fallbackIntervalMs);

    return () => {
      if (fallbackTimer.current) {
        clearInterval(fallbackTimer.current);
        fallbackTimer.current = null;
      }
    };
  }, [connected, fallbackFetcher, fallbackIntervalMs]);

  return { data, connected };
}

/**
 * Send commands over WebSocket. Throws when disconnected so caller can fall back to REST.
 */
export function useWsCommand(): {
  sendCommand: (action: string, params?: Record<string, any>) => Promise<any>;
  connected: boolean;
} {
  const [connected, setConnected] = useState(wsManager.isConnected());

  useEffect(() => {
    return wsManager.onConnectionChange(setConnected);
  }, []);

  const sendCommand = useCallback(
    (action: string, params: Record<string, any> = {}) => {
      return wsManager.sendCommand(action, params);
    },
    [],
  );

  return { sendCommand, connected };
}

/**
 * Returns WebSocket connection state for UI indicators.
 */
export function useWsConnectionState(): boolean {
  const [connected, setConnected] = useState(wsManager.isConnected());

  useEffect(() => {
    return wsManager.onConnectionChange(setConnected);
  }, []);

  return connected;
}
