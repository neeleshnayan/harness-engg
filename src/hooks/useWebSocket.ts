import { useEffect, useRef, useCallback, useState } from 'react';

interface WebSocketMessage {
  type: string;
  event_type?: string;
  event_id?: string;
  data?: any;
  timestamp?: string;
  address?: string;
  state?: string;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: (event?: CloseEvent) => void;
  onError?: (error: Event | Record<string, unknown>) => void;
  reconnectInterval?: number; // base delay in ms
  maxReconnectAttempts?: number | null; // null/undefined => unlimited
}

export const useWebSocket = (
  url: string,
  options: UseWebSocketOptions = {}
) => {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectInterval = 1000,
    maxReconnectAttempts = null
  } = options;

  // Create stable references to the callback functions to prevent unnecessary reconnections
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
  }, [onMessage, onOpen, onClose, onError]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isConnectingRef = useRef(false);
  const lastCloseRef = useRef<{ code: number; reason: string; wasClean: boolean } | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');

  const connect = useCallback(() => {
    // Skip connection if URL is empty (waiting for wallet address)
    if (!url) {
      return;
    }
    if (isConnectingRef.current || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    isConnectingRef.current = true;
    setConnectionStatus('connecting');

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        isConnectingRef.current = false;
        reconnectAttemptsRef.current = 0;
        lastCloseRef.current = null;
        setConnectionStatus('connected');
        onOpenRef.current?.();
      };

      ws.onmessage = (event) => {
        // Skip plain-text keepalive messages (e.g. "ping")
        if (typeof event.data === 'string' && !event.data.startsWith('{')) {
          return;
        }
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          onMessageRef.current?.(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        isConnectingRef.current = false;
        lastCloseRef.current = {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        };
        setConnectionStatus('disconnected');
        onCloseRef.current?.(event);

        // Attempt to reconnect if not manually closed.
        if (event.code !== 1000) {
          reconnectAttemptsRef.current += 1;

          // Optional max attempts; if reached, cool down then retry.
          if (
            maxReconnectAttempts &&
            maxReconnectAttempts > 0 &&
            reconnectAttemptsRef.current >= maxReconnectAttempts
          ) {
            console.error('Max reconnection attempts reached, retrying after cooldown');
            setConnectionStatus('error');
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current = 0;
              connect();
            }, 60000);
            return;
          }

          // Exponential backoff with jitter and upper cap.
          const cappedBaseDelay = Math.min(
            reconnectInterval * Math.pow(2, reconnectAttemptsRef.current - 1),
            30000
          );
          const jitterFactor = 0.8 + Math.random() * 0.4; // 0.8x..1.2x
          const reconnectDelay = Math.floor(cappedBaseDelay * jitterFactor);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectDelay);
        }
      };

      ws.onerror = (error) => {
        isConnectingRef.current = false;
        setConnectionStatus('error');
        // Browser websocket error events are often opaque ({}). Include contextual diagnostics.
        onErrorRef.current?.({
          type: 'websocket_error',
          readyState: ws.readyState,
          url,
          lastCloseCode: lastCloseRef.current?.code,
          lastCloseReason: lastCloseRef.current?.reason,
          lastCloseWasClean: lastCloseRef.current?.wasClean,
          originalEventType: error?.type,
        });
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      isConnectingRef.current = false;
      setConnectionStatus('error');
    }
  }, [url, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }

    isConnectingRef.current = false;
    reconnectAttemptsRef.current = 0;
    setConnectionStatus('disconnected');
  }, []);

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    setTimeout(connect, 1000);
  }, [connect, disconnect]);

  // Store URL in ref to track changes
  const urlRef = useRef(url);
  const prevUrlRef = useRef<string | null>(null);
  const isMountedRef = useRef(true);

  // Only reconnect if URL actually changes, not on every render
  useEffect(() => {
    isMountedRef.current = true;
    urlRef.current = url;

    // Only connect if URL changed or not already connected
    const urlChanged = prevUrlRef.current !== null && prevUrlRef.current !== url;
    const currentState = wsRef.current?.readyState;
    const notConnected = currentState !== WebSocket.OPEN && currentState !== WebSocket.CONNECTING;

    if (urlChanged || (notConnected && prevUrlRef.current === null)) {
      // If already connected to a different URL, disconnect first
      if (urlChanged && currentState === WebSocket.OPEN) {
        wsRef.current?.close(1000, 'URL changed');
      }
      // Only connect if component is still mounted
      if (isMountedRef.current) {
        connect();
      }
    }

    prevUrlRef.current = url;

    return () => {
      isMountedRef.current = false;
      // Only disconnect on unmount
      if (wsRef.current) {
        const state = wsRef.current.readyState;
        if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
          wsRef.current.close(1000, 'Component unmounting');
        }
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]); // Only depend on url, not connect/disconnect

  return {
    send,
    disconnect,
    reconnect,
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    readyState: wsRef.current?.readyState,
    connectionStatus
  };
};
