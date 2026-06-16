#!/usr/bin/env python3
"""
Mock n8n webhook server para pruebas end-to-end del QA Agent.

Uso:
    python tests/test_mock_n8n.py [puerto]

Por defecto escucha en el puerto 9299.
Imprime cada callback recibido con todos sus campos y el archivo adjunto.
Ctrl+C para detener.
"""

import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9299


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        ct = self.headers.get("Content-Type", "")
        body = self.rfile.read(length)
        self.send_response(200)
        self.end_headers()

        boundary = None
        for part in ct.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[9:].strip('"').encode()

        print(f"\n{'='*60}", flush=True)
        print(f"POST {self.path}", flush=True)
        print(f"Content-Type: {ct}", flush=True)
        print(f"{'='*60}", flush=True)

        if not boundary:
            print(f"[BODY]\n{body.decode('utf-8', errors='replace')}", flush=True)
            return

        parts = body.split(b"--" + boundary)
        for part in parts[1:-1]:
            header, _, content = part.partition(b"\r\n\r\n")
            content = content.rstrip(b"\r\n")
            hdr = header.decode("utf-8", errors="replace")

            if "filename=" in hdr:
                fname = hdr.split('filename="')[1].split('"')[0]
                print(f"\n[ARCHIVO] {fname}:", flush=True)
                print("-" * 50, flush=True)
                print(content.decode("utf-8", errors="replace"), flush=True)
                print("-" * 50, flush=True)
            else:
                name = hdr.split('name="')[1].split('"')[0]
                val = content.decode("utf-8", errors="replace")
                if name == "executive_summary":
                    print(f"\n[executive_summary]:\n{val}", flush=True)
                else:
                    print(f"  {name}: {val[:120]}", flush=True)

        print("\n[OK] Callback recibido correctamente — respondiendo 200\n", flush=True)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Mock n8n escuchando en http://0.0.0.0:{PORT}/webhook/qa-result")
    print("Apunta N8N_CALLBACK_URL o callback_url del request a esa URL.")
    print("Ctrl+C para detener.\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
