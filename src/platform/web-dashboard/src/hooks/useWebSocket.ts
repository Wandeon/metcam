import { useState, useEffect, useRef, useCallback } from 'react';
import { wsManager } from '@/services/websocket';

/**
 * Subscribe to a WebSocket channel with automatic REST fallback when disconnected.
 *
 * Fallback is disabled only after the FIRST WS data arrives for this channel,
 * not just when the WS reports "connected". This prevents data gaps when the
 * WS connects but hasn't delivered channel data yet (e.g. broadcast loop hasn't
 * ticked, or connection drops before first broadcast).
 */
export function useWsChannel<T>(
  channel: string,
  fallbackFetcher?: () => Promise<T>,
  fallbackIntervalMs?: number,
): { data: T | null; connected: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [connected, setConnected] = useState(wsManager.isConnected());
  // Track whether WS has delivered at least one message for this channel
  // since the last connection. Reset on disconnect.
  const wsDataReceived = useRef(false);
  const fallbackTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Track connection state
  useEffect(() => {
    return wsManager.onConnectionChange((isConnected) => {
      setConnected(isConnected);
      if (!isConnected) {
        wsDataReceived.current = false;
      }
    });
  }, []);

  // Subscribe to WS channel
  useEffect(() => {
    const unsub = wsManager.subscribe(channel, (channelData: T) => {
      wsDataReceived.current = true;
      setData(channelData);
    });
    return unsub;
  }, [channel]);

  // Fallback polling: runs until WS has delivered data for THIS channel.
  // This means REST keeps running during the WS "connected but no data yet"
  // window, preventing stale UI.
  useEffect(() => {
    const wsDelivering = connected && wsDataReceived.current;

    if (wsDelivering || !fallbackFetcher || !fallbackIntervalMs) {
      if (fallbackTimer.current) {
        clearInterval(fallbackTimer.current);
        fallbackTimer.current = null;
      }
      return;
    }

    // Fetch immediately on disconnect or initial mount
    fallbackFetcher().then(setData).catch(() => {});

    fallbackTimer.current = setInterval(() => {
      // Re-check: WS may have delivered data since the interval started
      if (wsDataReceived.current && wsManager.isConnected()) {
        if (fallbackTimer.current) {
          clearInterval(fallbackTimer.current);
          fallbackTimer.current = null;
        }
        return;
      }
      fallbackFetcher!().then(setData).catch(() => {});
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
