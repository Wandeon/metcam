import { wsManager } from '@/services/websocket';

const SIGNAL_TIMEOUT_MS = 12_000;

type StreamKind = 'main_cam0' | 'main_cam1' | 'panorama';

interface SessionReadyPayload {
  success: boolean;
  session_id: string;
  stream_kind: StreamKind;
  ice_servers?: Array<{ urls: string[]; username?: string; credential?: string }>;
  message?: string;
}

interface AnswerPayload {
  success: boolean;
  session_id: string;
  stream_kind: StreamKind;
  sdp: string;
  message?: string;
}

interface CandidatePayload {
  session_id: string;
  stream_kind: StreamKind;
  candidate: string;
  sdpMLineIndex: number;
}

interface PendingSignal<T> {
  resolve: (value: T) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

interface ActivePeer {
  streamKind: StreamKind;
  sessionId?: string;
  peer: RTCPeerConnection;
  queuedLocalCandidates: RTCIceCandidateInit[];
  video: HTMLVideoElement;
}

function normalizeIceUrl(url: string): string {
  return (url || '')
    .trim()
    .replace(/^stun:\/\//i, 'stun:')
    .replace(/^stuns:\/\//i, 'stuns:')
    .replace(/^turn:\/\//i, 'turn:')
    .replace(/^turns:\/\//i, 'turns:');
}

function normalizeIceServers(iceServers?: RTCIceServer[]): RTCIceServer[] | undefined {
  if (!iceServers?.length) return undefined;

  const normalized: RTCIceServer[] = [];
  for (const server of iceServers) {
    if (!server) continue;
    const urlsRaw = server.urls;
    const urls = (Array.isArray(urlsRaw) ? urlsRaw : [urlsRaw])
      .filter((u): u is string => typeof u === 'string' && u.trim().length > 0)
      .map(normalizeIceUrl);
    if (!urls.length) continue;

    const item: RTCIceServer = { urls };
    if (server.username) item.username = server.username;
    if (server.credential) item.credential = server.credential;
    normalized.push(item);
  }

  return normalized.length ? normalized : undefined;
}

class WebRtcService {
  private peersByStream = new Map<StreamKind, ActivePeer>();
  private peersBySession = new Map<string, ActivePeer>();
  private pendingReadyByStream = new Map<StreamKind, PendingSignal<SessionReadyPayload>>();
  private pendingAnswerBySession = new Map<string, PendingSignal<AnswerPayload>>();
  private initialized = false;
  private unsubs: Array<() => void> = [];

  init(): void {
    if (this.initialized) return;
    this.initialized = true;

    this.unsubs.push(
      wsManager.onMessageType('webrtc_session_ready', (msg) => {
        const data = msg?.data as SessionReadyPayload;
        const pending = this.pendingReadyByStream.get(data?.stream_kind);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pendingReadyByStream.delete(data.stream_kind);
        pending.resolve(data);
      }),
    );

    this.unsubs.push(
      wsManager.onMessageType('webrtc_answer', (msg) => {
        const data = msg?.data as AnswerPayload;
        const pending = this.pendingAnswerBySession.get(data?.session_id);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pendingAnswerBySession.delete(data.session_id);
        pending.resolve(data);
      }),
    );

    this.unsubs.push(
      wsManager.onMessageType('webrtc_ice_candidate', async (msg) => {
        const data = msg?.data as CandidatePayload;
        const peerState = this.peersBySession.get(data?.session_id);
        if (!peerState || !data?.candidate) return;
        try {
          await peerState.peer.addIceCandidate({
            candidate: data.candidate,
            sdpMLineIndex: data.sdpMLineIndex,
          });
        } catch (err) {
          console.warn('[WebRTC] Failed to add remote ICE candidate', err);
        }
      }),
    );

    this.unsubs.push(
      wsManager.onMessageType('webrtc_error', (msg) => {
        const data = msg?.data ?? {};
        const sessionId = data.session_id as string | undefined;
        const streamKind = data.stream_kind as StreamKind | undefined;
        const error = new Error(data.error || 'WebRTC signaling error');

        if (sessionId && this.pendingAnswerBySession.has(sessionId)) {
          const pending = this.pendingAnswerBySession.get(sessionId)!;
          clearTimeout(pending.timer);
          this.pendingAnswerBySession.delete(sessionId);
          pending.reject(error);
        }
        if (streamKind && this.pendingReadyByStream.has(streamKind)) {
          const pending = this.pendingReadyByStream.get(streamKind)!;
          clearTimeout(pending.timer);
          this.pendingReadyByStream.delete(streamKind);
          pending.reject(error);
        }
      }),
    );

    this.unsubs.push(
      wsManager.onConnectionChange((connected) => {
        if (connected) return;
        for (const streamKind of Array.from(this.peersByStream.keys())) {
          this.stopStream(streamKind);
        }
      }),
    );
  }

  async startStream(
    streamKind: StreamKind,
    video: HTMLVideoElement,
    iceServers?: RTCIceServer[],
  ): Promise<void> {
    this.init();
    this.stopStream(streamKind);

    if (!wsManager.isConnected()) {
      throw new Error('WebSocket not connected');
    }

    const peer = new RTCPeerConnection({
      iceServers: normalizeIceServers(iceServers) ?? [{ urls: ['stun:stun.l.google.com:19302'] }],
    });

    const state: ActivePeer = {
      streamKind,
      peer,
      video,
      queuedLocalCandidates: [],
    };
    this.peersByStream.set(streamKind, state);

    peer.ontrack = (event) => {
      const [remoteStream] = event.streams;
      if (remoteStream) {
        state.video.srcObject = remoteStream;
        state.video.play().catch(() => {});
      }
    };

    peer.onicecandidate = (event) => {
      if (!event.candidate) return;
      const candidateInit = event.candidate.toJSON();
      if (!state.sessionId) {
        state.queuedLocalCandidates.push(candidateInit);
        return;
      }
      wsManager.sendMessage('webrtc_ice_candidate', {
        session_id: state.sessionId,
        stream_kind: streamKind,
        candidate: candidateInit.candidate,
        sdpMLineIndex: candidateInit.sdpMLineIndex ?? 0,
      });
    };

    try {
      const ready = await this.awaitSessionReady(streamKind);
      if (!ready.success || !ready.session_id) {
        throw new Error(ready.message || 'Failed to create WebRTC session');
      }
      state.sessionId = ready.session_id;
      this.peersBySession.set(ready.session_id, state);

      if (ready.ice_servers?.length) {
        // If backend returns ICE config, recreate connection with those values.
        // Browser does not allow mutating iceServers in-place after construction.
        // Keep current behavior simple for this rollout and rely on current PC config.
      }

      const offer = await peer.createOffer({
        offerToReceiveAudio: false,
        offerToReceiveVideo: true,
      });
      await peer.setLocalDescription(offer);

      const answerPromise = this.awaitAnswer(ready.session_id);
      wsManager.sendMessage('webrtc_offer', {
        session_id: ready.session_id,
        stream_kind: streamKind,
        sdp: offer.sdp,
      });
      const answer = await answerPromise;
      if (!answer.success || !answer.sdp) {
        throw new Error(answer.message || 'Failed to receive WebRTC answer');
      }

      await peer.setRemoteDescription({
        type: 'answer',
        sdp: answer.sdp,
      });

      // Flush queued local ICE candidates after session is bound.
      for (const candidate of state.queuedLocalCandidates) {
        wsManager.sendMessage('webrtc_ice_candidate', {
          session_id: ready.session_id,
          stream_kind: streamKind,
          candidate: candidate.candidate,
          sdpMLineIndex: candidate.sdpMLineIndex ?? 0,
        });
      }
      state.queuedLocalCandidates = [];
    } catch (err) {
      this.stopStream(streamKind);
      throw err;
    }
  }

  stopStream(streamKind: StreamKind): void {
    const pendingReady = this.pendingReadyByStream.get(streamKind);
    if (pendingReady) {
      clearTimeout(pendingReady.timer);
      this.pendingReadyByStream.delete(streamKind);
      pendingReady.reject(new Error('WebRTC stream stopped'));
    }

    const state = this.peersByStream.get(streamKind);
    if (!state) return;

    if (state.sessionId) {
      const pendingAnswer = this.pendingAnswerBySession.get(state.sessionId);
      if (pendingAnswer) {
        clearTimeout(pendingAnswer.timer);
        this.pendingAnswerBySession.delete(state.sessionId);
        pendingAnswer.reject(new Error('WebRTC stream stopped'));
      }
      try {
        wsManager.sendMessage('webrtc_stop', { session_id: state.sessionId, stream_kind: streamKind });
      } catch {
        // Ignore signaling failures during teardown.
      }
      this.peersBySession.delete(state.sessionId);
    }

    try {
      state.peer.onicecandidate = null;
      state.peer.ontrack = null;
      state.peer.close();
    } catch {
      // Ignore teardown errors.
    }

    if (state.video.srcObject) {
      state.video.srcObject = null;
    }

    this.peersByStream.delete(streamKind);
  }

  shutdown(): void {
    for (const streamKind of Array.from(this.peersByStream.keys())) {
      this.stopStream(streamKind);
    }
    for (const unsub of this.unsubs) {
      unsub();
    }
    this.unsubs = [];
    this.initialized = false;
  }

  private awaitSessionReady(streamKind: StreamKind): Promise<SessionReadyPayload> {
    wsManager.sendMessage('webrtc_start', { stream_kind: streamKind });
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingReadyByStream.delete(streamKind);
        reject(new Error(`Timed out waiting for WebRTC session: ${streamKind}`));
      }, SIGNAL_TIMEOUT_MS);
      this.pendingReadyByStream.set(streamKind, { resolve, reject, timer });
    });
  }

  private awaitAnswer(sessionId: string): Promise<AnswerPayload> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingAnswerBySession.delete(sessionId);
        reject(new Error(`Timed out waiting for WebRTC answer: ${sessionId}`));
      }, SIGNAL_TIMEOUT_MS);
      this.pendingAnswerBySession.set(sessionId, { resolve, reject, timer });
    });
  }
}

export const webRtcService = new WebRtcService();
export type { StreamKind };
