#!/usr/bin/env python3
"""
MJPEG HTTP Server - Proxies GStreamer TCP streams to HTTP with proper headers
"""
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

class MJPEGHandler(BaseHTTPRequestHandler):
    def __init__(self, tcp_host, tcp_port, *args, **kwargs):
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        super().__init__(*args, **kwargs)

    def do_GET(self):
        sock = None
        try:
            # Send HTTP headers for MJPEG first
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=--videoboundary')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Connect to GStreamer TCP stream
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.tcp_host, self.tcp_port))

            # Stream data from TCP to HTTP
            while True:
                data = sock.recv(8192)
                if not data:
                    break
                self.wfile.write(data)
                self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError):
            pass  # Client disconnected
        except Exception as e:
            print(f"Stream error: {e}", file=sys.stderr)
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass

    def log_message(self, format, *args):
        # Silent logging
        pass

def start_proxy_server(http_port, tcp_host, tcp_port):
    def handler(*args, **kwargs):
        return MJPEGHandler(tcp_host, tcp_port, *args, **kwargs)

    server = HTTPServer(('0.0.0.0', http_port), handler)
    print(f"MJPEG proxy running: HTTP :{http_port} -> TCP {tcp_host}:{tcp_port}")
    server.serve_forever()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: mjpeg_http_server.py <http_port> <tcp_host> <tcp_port>")
        sys.exit(1)

    http_port = int(sys.argv[1])
    tcp_host = sys.argv[2]
    tcp_port = int(sys.argv[3])

    start_proxy_server(http_port, tcp_host, tcp_port)
