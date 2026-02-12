#!/usr/bin/env python3
"""
Preview service for FootballVision Pro.

Supports dual-camera preview with transport abstraction:
- HLS (legacy/default-safe)
- WebRTC (new low-latency path)
"""

import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from gstreamer_manager import GStreamerManager, PipelineState
import pipeline_builders
from exposure_sync_service import get_exposure_sync_service

logger = logging.getLogger(__name__)


Transport = str
HLS: Transport = "hls"
WEBRTC: Transport = "webrtc"


class PreviewService:
    """
    Manages dual-camera preview with transport selection.

    Recording/preview mutual exclusion is still enforced in the API layer
    via pipeline_manager; this service only handles preview lifecycle.
    """

    def __init__(self, hls_base_dir: str = "/dev/shm/hls"):
        self.hls_base_dir = Path(hls_base_dir)
        self.hls_base_dir.mkdir(parents=True, exist_ok=True)

        self.gst_manager = GStreamerManager()
        self.state_lock = Lock()

        # Camera IDs
        self.camera_ids = [0, 1]

        # Runtime mode: hls | webrtc | dual
        self.preview_transport_mode = os.getenv("PREVIEW_TRANSPORT_MODE", "dual").strip().lower()
        if self.preview_transport_mode not in {"hls", "webrtc", "dual"}:
            self.preview_transport_mode = "dual"

        # Track active state/transport
        self.preview_active = {cam_id: False for cam_id in self.camera_ids}
        self.preview_transport = {cam_id: HLS for cam_id in self.camera_ids}

        # WebRTC session state
        # session_id -> session metadata
        self.webrtc_sessions: Dict[str, Dict[str, Any]] = {}
        # connection_id -> set(session_id)
        self.connection_sessions: Dict[str, set[str]] = {}
        # Optional emitter callback: (connection_id, message_dict) -> None
        self.webrtc_emitter: Optional[Callable[[str, Dict[str, Any]], None]] = None
        # One-time callback registration guard per pipeline
        self.webrtc_callbacks_registered: set[str] = set()

        # STUN/TURN settings for webrtcbin
        self.stun_server = os.getenv("WEBRTC_STUN_SERVER", "stun://stun.l.google.com:19302").strip()
        self.turn_server = os.getenv("WEBRTC_TURN_SERVER", "").strip() or None

    # ---------------------------------------------------------------------
    # Transport + status
    # ---------------------------------------------------------------------

    def _resolve_transport(self, requested_transport: Optional[str]) -> Transport:
        requested = (requested_transport or "").strip().lower()
        if requested in {HLS, WEBRTC}:
            return requested
        if self.preview_transport_mode == WEBRTC:
            return WEBRTC
        # In dual mode default to HLS unless caller explicitly asks for WebRTC.
        return HLS

    def _is_webrtc_supported(self) -> bool:
        try:
            import gi
            gi.require_version("GstWebRTC", "1.0")
            gi.require_version("GstSdp", "1.0")
            from gi.repository import GstWebRTC, GstSdp  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _ice_server_for_browser(url: str) -> dict[str, Any] | None:
        """Return an RTCIceServer dict for browsers.

        Note: GStreamer webrtcbin uses stun/turn URLs like `stun://host:port`,
        but browsers expect `stun:host:port` (no `//`). This helper normalizes
        the common schemes and extracts TURN credentials into `username` and
        `credential` fields when provided.
        """
        raw = (url or "").strip()
        if not raw:
            return None

        # Already in browser-ish form (e.g., "stun:host:port").
        # We intentionally do not parse credentials from this variant.
        if "://" not in raw:
            return {"urls": [raw]}

        parsed = urlparse(raw)
        scheme = (parsed.scheme or "").lower()
        host = parsed.hostname
        port = parsed.port
        if scheme not in {"stun", "stuns", "turn", "turns"} or not host:
            return None

        browser_url = f"{scheme}:{host}"
        if port:
            browser_url += f":{port}"
        if scheme in {"turn", "turns"} and parsed.query:
            browser_url += f"?{parsed.query}"

        server: dict[str, Any] = {"urls": [browser_url]}
        if scheme in {"turn", "turns"}:
            if parsed.username:
                server["username"] = parsed.username
            if parsed.password:
                server["credential"] = parsed.password
        return server

    def get_ice_servers(self) -> list[dict[str, Any]]:
        """Return browser-compatible RTCIceServer config (for RTCPeerConnection)."""
        servers: list[dict[str, Any]] = []
        if self.stun_server:
            server = self._ice_server_for_browser(self.stun_server)
            if server:
                servers.append(server)
        if self.turn_server:
            server = self._ice_server_for_browser(self.turn_server)
            if server:
                servers.append(server)
        return servers

    def get_status(self) -> Dict[str, Any]:
        """Get current preview status."""
        with self.state_lock:
            cameras: Dict[str, Dict[str, Any]] = {}

            for cam_id in self.camera_ids:
                pipeline_name = f"preview_cam{cam_id}"
                info = self.gst_manager.get_pipeline_status(pipeline_name)

                active = bool(info and info.state == PipelineState.RUNNING)
                uptime = 0.0
                if info and info.start_time:
                    uptime = (datetime.utcnow() - info.start_time).total_seconds()

                transport = self.preview_transport.get(cam_id, HLS)
                stream_kind = f"main_cam{cam_id}"
                cameras[f"camera_{cam_id}"] = {
                    "active": active,
                    "state": info.state.value if info else "stopped",
                    "uptime": uptime,
                    # Backward-compatible field retained in dual-stack mode.
                    "hls_url": f"/hls/cam{cam_id}.m3u8",
                    "transport": transport,
                    "stream_kind": stream_kind,
                    "webrtc": {
                        "enabled": transport == WEBRTC,
                        "stream_kind": stream_kind,
                    },
                }
                self.preview_active[cam_id] = active

            active_webrtc_streams = [
                {
                    "session_id": sid,
                    "stream_kind": meta.get("stream_kind"),
                    "camera_id": meta.get("camera_id"),
                    "connection_id": meta.get("connection_id"),
                }
                for sid, meta in self.webrtc_sessions.items()
                if meta.get("active")
            ]

            return {
                "preview_active": any(cam["active"] for cam in cameras.values()),
                "cameras": cameras,
                "transport_mode": self.preview_transport_mode,
                "webrtc_supported": self._is_webrtc_supported(),
                "ice_servers": self.get_ice_servers(),
                "webrtc_streams": active_webrtc_streams,
            }

    # ---------------------------------------------------------------------
    # Preview lifecycle
    # ---------------------------------------------------------------------

    def _build_pipeline(self, cam_id: int, transport: Transport) -> str:
        if transport == WEBRTC:
            builder = getattr(pipeline_builders, "build_preview_webrtc_pipeline", None)
            if builder is None:
                raise RuntimeError("WebRTC pipeline builder is not available")
            return builder(
                camera_id=cam_id,
                stun_server=self.stun_server,
                turn_server=self.turn_server,
            )

        hls_location = str(self.hls_base_dir / f"cam{cam_id}.m3u8")
        return pipeline_builders.build_preview_pipeline(cam_id, hls_location)

    def start_preview(self, camera_id: Optional[int] = None, transport: Optional[str] = None) -> Dict[str, Any]:
        """
        Start preview for one or both cameras.

        Args:
            camera_id: Specific camera to start (0 or 1), or None for both.
            transport: Optional transport override (hls|webrtc).
        """
        with self.state_lock:
            resolved_transport = self._resolve_transport(transport)
            cameras_to_start = [camera_id] if camera_id is not None else self.camera_ids

            # Recreate HLS dir for legacy transport.
            if resolved_transport == HLS:
                self.hls_base_dir.mkdir(parents=True, exist_ok=True)

            started_cameras = []
            failed_cameras = []

            for cam_id in cameras_to_start:
                if cam_id not in self.camera_ids:
                    failed_cameras.append(cam_id)
                    continue

                pipeline_name = f"preview_cam{cam_id}"
                status = self.gst_manager.get_pipeline_status(pipeline_name)

                if status and status.state == PipelineState.RUNNING:
                    # If already running but with different transport, restart.
                    active_transport = self.preview_transport.get(cam_id, HLS)
                    if active_transport != resolved_transport:
                        self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=False, timeout=1.0)
                        self.gst_manager.remove_pipeline(pipeline_name)
                        self.webrtc_callbacks_registered.discard(pipeline_name)
                    else:
                        started_cameras.append(cam_id)
                        continue

                if status:
                    self.gst_manager.remove_pipeline(pipeline_name)
                    self.webrtc_callbacks_registered.discard(pipeline_name)

                try:
                    pipeline_str = self._build_pipeline(cam_id, resolved_transport)

                    def on_eos(name, metadata):
                        logger.info("Preview pipeline %s received EOS", name)

                    def on_error(name, error, debug, metadata):
                        logger.error("Preview pipeline %s error: %s, debug: %s", name, error, debug)

                    created = self.gst_manager.create_pipeline(
                        name=pipeline_name,
                        pipeline_description=pipeline_str,
                        on_eos=on_eos,
                        on_error=on_error,
                        metadata={
                            "camera_id": cam_id,
                            "transport": resolved_transport,
                        },
                    )
                    if not created:
                        failed_cameras.append(cam_id)
                        continue

                    # GStreamer 1.20's webrtcbin `turn-server` property validates
                    # the URL but doesn't register it with the ICE agent for relay
                    # allocation.  The `add-turn-server` action signal is the
                    # correct API and actually adds it to the relay list.
                    if resolved_transport == WEBRTC and self.turn_server:
                        webrtcbin = self._get_webrtcbin(pipeline_name)
                        if webrtcbin:
                            added = webrtcbin.emit("add-turn-server", self.turn_server)
                            logger.info("TURN server added to %s via signal: %s", pipeline_name, added)

                    if not self.gst_manager.start_pipeline(pipeline_name):
                        self.gst_manager.remove_pipeline(pipeline_name)
                        failed_cameras.append(cam_id)
                        continue

                    self.preview_active[cam_id] = True
                    self.preview_transport[cam_id] = resolved_transport
                    started_cameras.append(cam_id)
                    logger.info("Preview camera %s started (%s)", cam_id, resolved_transport)
                except Exception as e:
                    logger.error("Failed to start preview camera %s: %s", cam_id, e)
                    failed_cameras.append(cam_id)

            if not started_cameras:
                return {
                    "success": False,
                    "message": "Failed to start any preview cameras",
                    "failed_cameras": failed_cameras,
                }

            # Exposure sync is only useful for long-lived preview pipelines.
            exposure_service = get_exposure_sync_service(self.gst_manager)
            if exposure_service:
                exposure_service.start()

            return {
                "success": True,
                "message": f"Preview started for cameras: {started_cameras}",
                "transport": resolved_transport,
                "cameras_started": started_cameras,
                "cameras_failed": failed_cameras,
            }

    def _clear_camera_sessions(self, cam_id: int) -> None:
        to_remove = [sid for sid, meta in self.webrtc_sessions.items() if meta.get("camera_id") == cam_id]
        for sid in to_remove:
            meta = self.webrtc_sessions.pop(sid, {})
            conn = meta.get("connection_id")
            if conn and conn in self.connection_sessions:
                self.connection_sessions[conn].discard(sid)
                if not self.connection_sessions[conn]:
                    del self.connection_sessions[conn]

    def stop_preview(self, camera_id: Optional[int] = None) -> Dict[str, Any]:
        """Stop preview for one or both cameras."""
        with self.state_lock:
            cameras_to_stop = [camera_id] if camera_id is not None else self.camera_ids

            stop_exposure_sync = camera_id is None
            if stop_exposure_sync:
                exposure_service = get_exposure_sync_service()
                if exposure_service:
                    exposure_service.stop()

            stopped_cameras = []
            failed_cameras = []

            for cam_id in cameras_to_stop:
                if cam_id not in self.camera_ids:
                    failed_cameras.append(cam_id)
                    continue

                pipeline_name = f"preview_cam{cam_id}"
                try:
                    stopped = self.gst_manager.stop_pipeline(
                        pipeline_name,
                        wait_for_eos=False,
                        timeout=1.0,
                    )
                    if not stopped:
                        failed_cameras.append(cam_id)
                        continue

                    self.preview_active[cam_id] = False
                    self.preview_transport[cam_id] = HLS
                    self.webrtc_callbacks_registered.discard(pipeline_name)
                    self._clear_camera_sessions(cam_id)
                    stopped_cameras.append(cam_id)
                except Exception as e:
                    logger.error("Failed to stop preview camera %s: %s", cam_id, e)
                    failed_cameras.append(cam_id)

            if not stopped_cameras:
                return {
                    "success": False,
                    "message": "No preview cameras were stopped",
                    "failed_cameras": failed_cameras,
                }

            return {
                "success": True,
                "message": f"Preview stopped for cameras: {stopped_cameras}",
                "cameras_stopped": stopped_cameras,
                "cameras_failed": failed_cameras,
            }

    def restart_preview(self, camera_id: Optional[int] = None, transport: Optional[str] = None) -> Dict[str, Any]:
        stop_result = self.stop_preview(camera_id)
        start_result = self.start_preview(camera_id, transport=transport)
        return {
            "success": start_result["success"],
            "message": f"Restart: {stop_result['message']} -> {start_result['message']}",
            "stop_result": stop_result,
            "start_result": start_result,
        }

    # ---------------------------------------------------------------------
    # WebRTC signaling/session handling
    # ---------------------------------------------------------------------

    def set_webrtc_emitter(self, emitter: Callable[[str, Dict[str, Any]], None]) -> None:
        self.webrtc_emitter = emitter

    def _emit_webrtc(self, connection_id: str, message: Dict[str, Any]) -> None:
        if self.webrtc_emitter is None:
            return
        try:
            self.webrtc_emitter(connection_id, message)
        except Exception as e:
            logger.error("Failed to emit WebRTC message: %s", e)

    def _get_webrtcbin(self, pipeline_name: str):
        with self.gst_manager.pipelines_lock:
            entry = self.gst_manager.pipelines.get(pipeline_name)
            if not entry:
                return None
            pipeline = entry.get("pipeline")
            if pipeline is None:
                return None
            return pipeline.get_by_name("webrtc")

    def _register_webrtc_callbacks(self, pipeline_name: str) -> None:
        if pipeline_name in self.webrtc_callbacks_registered:
            return

        webrtcbin = self._get_webrtcbin(pipeline_name)
        if webrtcbin is None:
            raise RuntimeError(f"webrtcbin not found in {pipeline_name}")

        def on_ice_candidate(_element, mlineindex, candidate):
            # Emit candidate for every active session attached to this pipeline.
            for sid, meta in list(self.webrtc_sessions.items()):
                if meta.get("pipeline_name") != pipeline_name or not meta.get("active"):
                    continue
                self._emit_webrtc(
                    meta["connection_id"],
                    {
                        "v": 1,
                        "type": "webrtc_ice_candidate",
                        "data": {
                            "session_id": sid,
                            "stream_kind": meta.get("stream_kind"),
                            "candidate": candidate,
                            "sdpMLineIndex": mlineindex,
                        },
                    },
                )

        webrtcbin.connect("on-ice-candidate", on_ice_candidate)
        self.webrtc_callbacks_registered.add(pipeline_name)

    def create_webrtc_session(self, connection_id: str, stream_kind: str) -> Dict[str, Any]:
        """
        Allocate/create a WebRTC session for a preview stream kind.
        stream_kind: main_cam0 | main_cam1
        """
        if not self._is_webrtc_supported():
            return {"success": False, "message": "WebRTC runtime is not available"}

        if stream_kind not in {"main_cam0", "main_cam1"}:
            return {"success": False, "message": f"Unsupported stream_kind: {stream_kind}"}

        cam_id = 0 if stream_kind.endswith("0") else 1
        should_start = False
        with self.state_lock:
            active_transport = self.preview_transport.get(cam_id, HLS)
            active_state = self.preview_active.get(cam_id, False)
            should_start = not active_state or active_transport != WEBRTC

        if should_start:
            start = self.start_preview(camera_id=cam_id, transport=WEBRTC)
            if not start.get("success"):
                return {"success": False, "message": start.get("message", "Failed to start WebRTC preview")}

        with self.state_lock:
            session_id = str(uuid.uuid4())
            pipeline_name = f"preview_cam{cam_id}"
            self._register_webrtc_callbacks(pipeline_name)

            self.webrtc_sessions[session_id] = {
                "session_id": session_id,
                "connection_id": connection_id,
                "camera_id": cam_id,
                "stream_kind": stream_kind,
                "pipeline_name": pipeline_name,
                "active": True,
                "created_at": time.time(),
            }
            self.connection_sessions.setdefault(connection_id, set()).add(session_id)

            return {
                "success": True,
                "session_id": session_id,
                "stream_kind": stream_kind,
                "camera_id": cam_id,
                "ice_servers": self.get_ice_servers(),
            }

    def _parse_offer(self, sdp_offer: str):
        import gi
        gi.require_version("GstWebRTC", "1.0")
        gi.require_version("GstSdp", "1.0")
        from gi.repository import GstWebRTC, GstSdp

        _, sdpmsg = GstSdp.SDPMessage.new()
        GstSdp.sdp_message_parse_buffer(bytes(sdp_offer.encode("utf-8")), sdpmsg)
        return GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdpmsg)

    def handle_webrtc_offer(self, connection_id: str, session_id: str, sdp_offer: str) -> Dict[str, Any]:
        with self.state_lock:
            session = self.webrtc_sessions.get(session_id)
            if not session:
                return {"success": False, "message": "Unknown session_id"}
            if session.get("connection_id") != connection_id:
                return {"success": False, "message": "Session does not belong to this connection"}

            pipeline_name = session["pipeline_name"]
            webrtcbin = self._get_webrtcbin(pipeline_name)
            if webrtcbin is None:
                return {"success": False, "message": "webrtcbin not found"}

            try:
                offer = self._parse_offer(sdp_offer)
                import gi
                gi.require_version("Gst", "1.0")
                from gi.repository import Gst

                set_remote = Gst.Promise.new()
                webrtcbin.emit("set-remote-description", offer, set_remote)
                set_remote.interrupt()

                create_answer = Gst.Promise.new()
                webrtcbin.emit("create-answer", None, create_answer)
                create_answer.wait()
                reply = create_answer.get_reply()
                answer = reply.get_value("answer")

                set_local = Gst.Promise.new()
                webrtcbin.emit("set-local-description", answer, set_local)
                set_local.interrupt()

                return {
                    "success": True,
                    "session_id": session_id,
                    "stream_kind": session.get("stream_kind"),
                    "sdp": answer.sdp.as_text(),
                }
            except Exception as e:
                logger.error("Failed handling WebRTC offer: %s", e)
                return {"success": False, "message": str(e)}

    def add_webrtc_ice_candidate(
        self,
        connection_id: str,
        session_id: str,
        candidate: str,
        sdp_mline_index: int,
    ) -> Dict[str, Any]:
        with self.state_lock:
            session = self.webrtc_sessions.get(session_id)
            if not session:
                return {"success": False, "message": "Unknown session_id"}
            if session.get("connection_id") != connection_id:
                return {"success": False, "message": "Session does not belong to this connection"}

            webrtcbin = self._get_webrtcbin(session["pipeline_name"])
            if webrtcbin is None:
                return {"success": False, "message": "webrtcbin not found"}

            try:
                webrtcbin.emit("add-ice-candidate", int(sdp_mline_index), candidate)
                return {"success": True}
            except Exception as e:
                logger.error("Failed to add ICE candidate: %s", e)
                return {"success": False, "message": str(e)}

    def stop_webrtc_session(self, connection_id: str, session_id: str) -> Dict[str, Any]:
        camera_to_stop: Optional[int] = None
        with self.state_lock:
            session = self.webrtc_sessions.get(session_id)
            if not session:
                return {"success": False, "message": "Unknown session_id"}
            if session.get("connection_id") != connection_id:
                return {"success": False, "message": "Session does not belong to this connection"}

            cam_id = session.get("camera_id")
            self.webrtc_sessions.pop(session_id, None)
            self.connection_sessions.get(connection_id, set()).discard(session_id)

            # If no more sessions on this camera, stop preview camera.
            remaining = [
                sid for sid, meta in self.webrtc_sessions.items()
                if meta.get("camera_id") == cam_id and meta.get("active")
            ]
            if not remaining and cam_id is not None:
                camera_to_stop = cam_id

        if camera_to_stop is not None:
            self.stop_preview(camera_id=camera_to_stop)

        return {"success": True}

    def clear_connection_sessions(self, connection_id: str) -> None:
        cameras_to_consider: set[int] = set()
        with self.state_lock:
            session_ids = list(self.connection_sessions.get(connection_id, set()))
            for sid in session_ids:
                meta = self.webrtc_sessions.pop(sid, None) or {}
                cam_id = meta.get("camera_id")
                if isinstance(cam_id, int):
                    cameras_to_consider.add(cam_id)
            self.connection_sessions.pop(connection_id, None)

        for cam_id in cameras_to_consider:
            active_for_camera = any(
                meta.get("camera_id") == cam_id and meta.get("active")
                for meta in self.webrtc_sessions.values()
            )
            if not active_for_camera:
                self.stop_preview(camera_id=cam_id)

    # ---------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------

    def cleanup(self):
        logger.info("PreviewService cleanup")
        for cam_id in self.camera_ids:
            if self.preview_active.get(cam_id):
                try:
                    self.stop_preview(cam_id)
                except Exception as e:
                    logger.error("Error stopping preview camera %s during cleanup: %s", cam_id, e)


# Global instance
_preview_service: Optional[PreviewService] = None


def get_preview_service() -> PreviewService:
    """Get or create the global PreviewService instance."""
    global _preview_service
    if _preview_service is None:
        _preview_service = PreviewService()
    return _preview_service
