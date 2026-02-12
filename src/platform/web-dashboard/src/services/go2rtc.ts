/**
 * go2rtc WebSocket signaling service.
 *
 * Protocol (go2rtc native WS):
 *   WS connect -> /api/ws?src=<stream>
 *   Client sends: { type: "webrtc/offer", value: "<SDP>" }
 *   Server sends: { type: "webrtc/answer", value: "<SDP>" }
 *   Both send:    { type: "webrtc/candidate", value: "<candidate string>" }
 */

type StreamKind = 'main_cam0' | 'main_cam1' | 'panorama';

/** Map stream kind to go2rtc stream name. */
function streamName(kind: StreamKind): string {
  switch (kind) {
    case 'main_cam0': return 'cam0';
    case 'main_cam1': return 'cam1';
    case 'panorama': return 'panorama';
    default: return kind;
  }
}

/** Build go2rtc WS URL from relay base URL + stream kind. */
export function buildGo2RtcWsUrl(relayBaseUrl: string, kind: StreamKind): string {
  const base = relayBaseUrl.replace(/\/+$/, '');
  return `${base}/api/ws?src=${streamName(kind)}`;
}

interface Go2RtcSession {
  pc: RTCPeerConnection;
  ws: WebSocket;
  streamKind: StreamKind;
  video: HTMLVideoElement;
}

class Go2RtcService {
  private sessions = new Map<StreamKind, Go2RtcSession>();

  async startStream(
    relayWsUrl: string,
    streamKind: StreamKind,
    video: HTMLVideoElement,
  ): Promise<void> {
    this.stopStream(streamKind);

    const wsUrl = buildGo2RtcWsUrl(relayWsUrl, streamKind);

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    });

    const session: Go2RtcSession = { pc, ws: null!, streamKind, video };
    this.sessions.set(streamKind, session);

    pc.ontrack = (event) => {
      const [remoteStream] = event.streams;
      if (remoteStream) {
        video.srcObject = remoteStream;
        video.play().catch(() => {});
      }
    };

    pc.addTransceiver('video', { direction: 'recvonly' });

    return new Promise<void>((resolve, reject) => {
      const ws = new WebSocket(wsUrl);
      session.ws = ws;

      const timeout = setTimeout(() => {
        reject(new Error('go2rtc signaling timeout'));
        this.stopStream(streamKind);
      }, 15_000);

      ws.onopen = async () => {
        try {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          ws.send(JSON.stringify({
            type: 'webrtc/offer',
            value: offer.sdp,
          }));
        } catch (err) {
          clearTimeout(timeout);
          reject(err instanceof Error ? err : new Error(String(err)));
          this.stopStream(streamKind);
        }
      };

      ws.onmessage = async (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'webrtc/answer') {
            await pc.setRemoteDescription(
              new RTCSessionDescription({ type: 'answer', sdp: msg.value }),
            );
            clearTimeout(timeout);
            resolve();
          } else if (msg.type === 'webrtc/candidate') {
            // go2rtc sends candidate as a string, not a JSON object.
            // Ignore empty candidates (end-of-candidates signal).
            const raw = msg.value;
            if (typeof raw === 'string' && raw.length > 0) {
              await pc.addIceCandidate({ candidate: raw, sdpMLineIndex: 0 });
            }
          }
        } catch (err) {
          console.warn('[go2rtc] Message handling error:', err);
        }
      };

      ws.onerror = () => {
        clearTimeout(timeout);
        reject(new Error('go2rtc WebSocket connection failed'));
        this.stopStream(streamKind);
      };

      ws.onclose = () => {
        if (this.sessions.get(streamKind) === session) {
          this.sessions.delete(streamKind);
        }
      };

      // Send local ICE candidates as strings (go2rtc protocol).
      pc.onicecandidate = (event) => {
        if (event.candidate && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'webrtc/candidate',
            value: event.candidate.candidate,
          }));
        }
      };
    });
  }

  stopStream(streamKind: StreamKind): void {
    const session = this.sessions.get(streamKind);
    if (!session) return;
    this.sessions.delete(streamKind);

    try { session.ws.close(); } catch { /* ignore */ }
    try {
      session.pc.onicecandidate = null;
      session.pc.ontrack = null;
      session.pc.close();
    } catch { /* ignore */ }
    if (session.video.srcObject) {
      session.video.srcObject = null;
    }
  }

  stopAll(): void {
    for (const kind of Array.from(this.sessions.keys())) {
      this.stopStream(kind);
    }
  }
}

export const go2RtcService = new Go2RtcService();
export type { StreamKind };
