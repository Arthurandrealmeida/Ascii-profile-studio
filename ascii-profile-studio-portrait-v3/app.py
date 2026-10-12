"""Loopback-only editor with origin checks and safe local file APIs."""
from __future__ import annotations

import argparse
import ipaddress
import io
import json
import os
import secrets
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps, UnidentifiedImageError
from generator import (ROOT, DEFAULT_CONFIG, load_config, normalize_config,
                       locate_photo, render_svg, render_portrait_svg, generate, write_config, atomic_write)
from github_stats import fetch_stats

MAX_BODY = 15 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = 'ASCIIProfileStudio/3'

    def respond(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Referrer-Policy', 'no-referrer')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, status, data):
        self.respond(status, json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def check_security(self, changing=False):
        # DNS rebinding guard: Host must match local names (or explicit bind host).
        host = self.headers.get('Host', '')
        host_url = urlparse('http://' + host)
        hostname = (host_url.hostname or '').lower()
        if host_url.port is not None and host_url.port != self.server.server_address[1]:
            raise PermissionError('Porta no Host não autorizada.')
        allowed = {'localhost', '127.0.0.1', '::1'}
        if not self.server.allow_remote and hostname not in allowed:
            raise PermissionError('Host não permitido. Use localhost ou 127.0.0.1.')
        if self.server.allow_remote and hostname not in allowed | {self.server.server_address[0].lower()}:
            raise PermissionError('Host não permitido.')
        if not self.server.allow_remote:
            try:
                peer = ipaddress.ip_address(self.client_address[0])
                if not peer.is_loopback:
                    raise PermissionError('Acesso restrito ao próprio computador.')
            except ValueError as err:
                raise PermissionError('Endereço do cliente inválido.') from err
        if changing:
            origin = self.headers.get('Origin', '')
            if origin:
                parsed = urlparse(origin)
                origin_hosts = allowed | ({self.server.server_address[0].lower()} if self.server.allow_remote else set())
                if parsed.scheme != 'http' or parsed.hostname not in origin_hosts or parsed.port != self.server.server_address[1]:
                    raise PermissionError('Origem não autorizada.')
            if self.headers.get('Sec-Fetch-Site', '').lower() in ('cross-site', 'same-site'):
                raise PermissionError('Requisição entre sites não permitida.')

    def body(self, json_required=False):
        if json_required and self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise ValueError('Content-Type esperado: application/json.')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError as err:
            raise ValueError('Content-Length inválido.') from err
        if not 0 < length <= MAX_BODY:
            raise ValueError('Requisição vazia ou acima do limite de 15 MB.')
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError('Dados enviados de forma incompleta.')
        return data

    def json_body(self):
        data = json.loads(self.body(json_required=True))
        if not isinstance(data, dict):
            raise ValueError('Corpo JSON deve ser um objeto.')
        return data

    def do_GET(self):
        try:
            self.check_security()
            parsed = urlparse(self.path)
            path = parsed.path
            if path == '/':
                self.respond(200, (ROOT/'static'/'index.html').read_bytes(), 'text/html; charset=utf-8')
            elif path in ('/static/app.js', '/static/style.css'):
                target = (ROOT/'static'/path.rsplit('/', 1)[-1])
                kind = 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8'
                self.respond(200, target.read_bytes(), kind)
            elif path == '/api/config':
                self.send_json(200, load_config())
            elif path == '/api/photo-preview':
                photo = parse_qs(parsed.query).get('path', [''])[0]
                source = locate_photo(photo)
                if source.stat().st_size > MAX_BODY:
                    raise ValueError('Foto maior que o limite.')
                with Image.open(source) as picture:
                    thumb = ImageOps.exif_transpose(picture).convert('RGBA')
                    thumb.thumbnail((1200, 1200))
                memory = io.BytesIO()
                thumb.save(memory, 'PNG')
                self.respond(200, memory.getvalue(), 'image/png')
            elif path in ('/preview.svg', '/preview-light.svg'):
                self.respond(200, render_svg(load_config(), light=path.endswith('light.svg')), 'image/svg+xml; charset=utf-8')
            elif path in ('/download/dark_mode.svg', '/download/light_mode.svg'):
                self.respond(200, render_svg(load_config(), light='light' in path), 'image/svg+xml; charset=utf-8',
                             {'Content-Disposition': 'attachment; filename="' + path.rsplit('/', 1)[-1] + '"'})
            else:
                self.send_json(404, {'error':'Não encontrado'})
        except Exception as exc:
            self.error(exc)

    def do_POST(self):
        try:
            self.check_security(changing=True)
            path = urlparse(self.path).path
            if path == '/api/photo':
                allowed_type = self.headers.get('Content-Type', '').split(';')[0]
                if allowed_type not in ('image/png', 'image/jpeg', 'image/webp', 'application/octet-stream'):
                    raise ValueError('Formato enviado não permitido.')
                with Image.open(io.BytesIO(self.body())) as image:
                    if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 25_000_000:
                        raise ValueError('Use PNG, JPEG ou WebP de até 25 megapixels.')
                    photo = ImageOps.exif_transpose(image).convert('RGBA')
                photo.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                memory = io.BytesIO()
                photo.save(memory, 'PNG', optimize=True)
                name = f'portrait-{secrets.token_hex(8)}.png'
                folder = ROOT/'assets'/'uploads'
                target = folder/name
                atomic_write(target, memory.getvalue())
                self.send_json(200, {'ok': True, 'path': 'assets/uploads/'+name})
            elif path in ('/api/render', '/api/export', '/api/save', '/api/export-portrait'):
                raw = self.json_body()
                config = normalize_config(raw)
                if path == '/api/export-portrait':
                    self.respond(200, render_portrait_svg(config), 'image/svg+xml; charset=utf-8',
                                 {'Content-Disposition': 'attachment; filename="portrait_only.svg"'})
                elif path == '/api/save':
                    # Validate and render before changing config.yaml or outputs.
                    render_svg(config)
                    render_svg(config, light=True)
                    generate(config)
                    write_config(config)
                    self.send_json(200, {'ok': True, 'files': ['output/dark_mode.svg', 'output/light_mode.svg', 'output/portrait_only.svg']})
                else:
                    light = bool(raw.get('preview_light', False)) if path == '/api/render' else raw.get('variant') == 'light'
                    svg = render_svg(config, light=light)
                    headers = ({'Content-Disposition': f'attachment; filename="{"light" if light else "dark"}_mode.svg"'}
                               if path == '/api/export' else None)
                    self.respond(200, svg, 'image/svg+xml; charset=utf-8', headers)
            elif path == '/api/stats':
                raw = self.json_body()
                self.send_json(200, fetch_stats(raw.get('username', '')))
            else:
                self.send_json(404, {'error': 'Não encontrado'})
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        status = 403 if isinstance(exc, PermissionError) else 400
        if isinstance(exc, (json.JSONDecodeError, UnidentifiedImageError, Image.DecompressionBombError, ValueError, TypeError, PermissionError, OSError)):
            self.send_json(status, {'error': str(exc)[:400]})
        else:
            # No raw server errors leaked to the browser.
            self.send_json(500, {'error': 'Erro interno. Confira o terminal.'})
            raise exc


def main():
    parser = argparse.ArgumentParser(description='Editor local de perfil ASCII')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=8765, type=int)
    parser.add_argument('--allow-remote', action='store_true', help='Permitir explicitamente exposição na rede (não recomendado)')
    parser.add_argument('--generate', action='store_true')
    options = parser.parse_args()
    if options.generate:
        for path in generate(load_config()):
            print(path)
        return
    if options.host not in ('127.0.0.1', 'localhost', '::1') and not options.allow_remote:
        parser.error('Para usar --host na rede, acrescente --allow-remote conscientemente.')
    if options.allow_remote:
        print('AVISO: editor exposto na rede. Não use em redes não confiáveis.', flush=True)
    server = ThreadingHTTPServer((options.host, options.port), Handler)
    server.allow_remote = options.allow_remote
    print(f'Editor pronto em http://{options.host}:{options.port} (Ctrl+C para sair)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
