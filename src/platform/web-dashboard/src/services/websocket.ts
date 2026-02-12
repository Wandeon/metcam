/**
 * WebSocket Manager for FootballVision Pro
 * Single persistent connection with auto-reconnection, channel subscriptions,
 * and two-phase command responses.
 *
 * Resilience features:
 * - Receive timeout: detects half-open/dead connections within 15s
 * - Fast initial reconnect (300ms) with exponential backoff to 30s
 * - Ping every 15s keeps proxy chains alive
 */

const PROTOCOL_VERSION = 1;
const PING_INTERVAL_MS = 15_000;
const COMMAND_TIMEOUT_MS = 30_000;
const RECONNECT_BASE_MS = 300;
const RECONNECT_MAX_MS = 30_000;
/** Force reconnect if no message received within this window. Server pushes
 *  status every 1s, so 15s of silence means the connection is dead. */
const RECEIVE_TIMEOUT_MS = 15_000;

type MessageHandler = (data: any) => void;
type TypedMessageHandler = (message: any) => void;
type ConnectionHandler = (connected: boolean) => void;

interface PendingCommand {
  resolve: (data: any) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string = '';
  private connected = false;
  private ready = false;
  private reconnectDelay = RECONNECT_BASE_MS;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;
  private lastReceivedAt = 0;

  private channelHandlers = new Map<string, Set<MessageHandler>>();
  private typedMessageHandlers = new Map<string, Set<TypedMessageHandler>>();
  private connectionHandlers = new Set<ConnectionHandler>();
  private pendingCommands = new Map<string, PendingCommand>();
  private commandCounter = 0;

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.intentionalClose = false;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${proto}//${window.location.host}/ws`;

    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      // Wait for hello before marking as connected
    };

    this.ws.onmessage = (event) => {
      this.handleMessage(event.data);
    };

    this.ws.onclose = () => {
      this.handleDisconnect();
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.cleanup();
  }

  subscribe(channel: string, handler: MessageHandler): () => void {
    if (!this.channelHandlers.has(channel)) {
      this.channelHandlers.set(channel, new Set());
    }
    this.channelHandlers.get(channel)!.add(handler);

    // Send subscribe if connected
    if (this.ready) {
      this.send({ v: PROTOCOL_VERSION, type: 'subscribe', channels: [channel] });
    }

    return () => {
      const handlers = this.channelHandlers.get(channel);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.channelHandlers.delete(channel);
          if (this.ready) {
            this.send({ v: PROTOCOL_VERSION, type: 'unsubscribe', channels: [channel] });
          }
        }
      }
    };
  }

  sendCommand(action: string, params: Record<string, any> = {}): Promise<any> {
    if (!this.ready) {
      return Promise.reject(new Error('WebSocket not connected'));
    }

    const id = `cmd_${++this.commandCounter}_${Date.now()}`;

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingCommands.delete(id);
        reject(new Error(`Command '${action}' timed out after ${COMMAND_TIMEOUT_MS / 1000}s`));
      }, COMMAND_TIMEOUT_MS);

      this.pendingCommands.set(id, { resolve, reject, timer });

      this.send({
        v: PROTOCOL_VERSION,
        type: 'command',
        id,
        action,
        params,
      });
    });
  }

  sendMessage(type: string, data: Record<string, any> = {}): void {
    if (!this.ready) {
      throw new Error('WebSocket not connected');
    }

    this.send({
      v: PROTOCOL_VERSION,
      type,
      data,
    });
  }

  onMessageType(type: string, handler: TypedMessageHandler): () => void {
    if (!this.typedMessageHandlers.has(type)) {
      this.typedMessageHandlers.set(type, new Set());
    }
    this.typedMessageHandlers.get(type)!.add(handler);
    return () => {
      const handlers = this.typedMessageHandlers.get(type);
      if (!handlers) return;
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.typedMessageHandlers.delete(type);
      }
    };
  }

  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    // Immediately notify current state
    handler(this.connected);
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  isConnected(): boolean {
    return this.connected;
  }

  // ========================================================================
  // Internal
  // ========================================================================

  private handleMessage(raw: string): void {
    let msg: any;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }

    // Every received message resets the receive timeout clock.
    this.lastReceivedAt = Date.now();

    const type = msg.type;

    if (type === 'hello') {
      this.ready = true;
      this.connected = true;
      this.reconnectDelay = RECONNECT_BASE_MS;
      this.startPing();
      this.notifyConnectionChange(true);

      // Subscribe to all currently-registered channels
      const channels = Array.from(this.channelHandlers.keys());
      if (channels.length > 0) {
        this.send({ v: PROTOCOL_VERSION, type: 'subscribe', channels });
      }
      return;
    }

    if (type === 'pong') {
      return;
    }

    if (type === 'command_ack') {
      // Optional: could trigger UI "processing" state
      return;
    }

    if (type === 'command_result') {
      const pending = this.pendingCommands.get(msg.id);
      if (pending) {
        clearTimeout(pending.timer);
        this.pendingCommands.delete(msg.id);
        if (msg.success) {
          pending.resolve(msg.data);
        } else {
          pending.reject(new Error(msg.error || 'Command failed'));
        }
      }
      return;
    }

    if (type === 'error') {
      console.warn('[WS] Server error:', msg.code, msg.message);
      return;
    }

    // Channel data message (status, system_metrics, pipeline_state, panorama_status)
    const handlers = this.channelHandlers.get(type);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(msg.data);
        } catch (e) {
          console.error(`[WS] Handler error for ${type}:`, e);
        }
      }
    }

    const typedHandlers = this.typedMessageHandlers.get(type);
    if (typedHandlers) {
      for (const handler of typedHandlers) {
        try {
          handler(msg);
        } catch (e) {
          console.error(`[WS] Typed handler error for ${type}:`, e);
        }
      }
    }
  }

  private handleDisconnect(): void {
    const wasConnected = this.connected;
    this.connected = false;
    this.ready = false;
    this.stopPing();
    this.ws = null;

    if (wasConnected) {
      this.notifyConnectionChange(false);
    }

    // Reject all pending commands
    for (const pending of this.pendingCommands.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error('WebSocket disconnected'));
    }
    this.pendingCommands.clear();

    if (!this.intentionalClose) {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);
  }

  private startPing(): void {
    this.stopPing();
    this.lastReceivedAt = Date.now();
    this.pingTimer = setInterval(() => {
      // Dead connection detection: if no message received within the timeout
      // window, the connection is half-open. Force close and reconnect.
      if (this.lastReceivedAt > 0 && Date.now() - this.lastReceivedAt > RECEIVE_TIMEOUT_MS) {
        console.warn('[WS] No message received in', RECEIVE_TIMEOUT_MS / 1000, 's — forcing reconnect');
        this.forceReconnect();
        return;
      }
      this.send({ v: PROTOCOL_VERSION, type: 'ping' });
    }, PING_INTERVAL_MS);
  }

  private forceReconnect(): void {
    this.stopPing();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      try { this.ws.close(); } catch { /* ignore */ }
      this.ws = null;
    }
    const wasConnected = this.connected;
    this.connected = false;
    this.ready = false;
    if (wasConnected) {
      this.notifyConnectionChange(false);
    }
    // Reject pending commands
    for (const pending of this.pendingCommands.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error('WebSocket receive timeout'));
    }
    this.pendingCommands.clear();
    // Reconnect immediately (don't wait for backoff)
    this.reconnectDelay = RECONNECT_BASE_MS;
    this.scheduleReconnect();
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private send(msg: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private notifyConnectionChange(connected: boolean): void {
    for (const handler of this.connectionHandlers) {
      try {
        handler(connected);
      } catch (e) {
        console.error('[WS] Connection handler error:', e);
      }
    }
  }

  private cleanup(): void {
    this.stopPing();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    this.ready = false;
    this.notifyConnectionChange(false);

    for (const [, pending] of this.pendingCommands) {
      clearTimeout(pending.timer);
      pending.reject(new Error('WebSocket disconnected'));
    }
    this.pendingCommands.clear();
  }
}

// Singleton
export const wsManager = new WebSocketManager();
