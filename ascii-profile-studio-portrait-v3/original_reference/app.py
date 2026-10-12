"""Local-only web editor for an ASCII GitHub profile SVG."""
from __future__ import annotations

import argparse
import io
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from PIL import Image, ImageOps
import yaml
from generator import ROOT, DEFAULT_CONFIG, load_config, normalize_config, render_svg, generate

MAX_BODY = 15 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', 'http://127.0.0.1:8765')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def json(self, status, data):
        self.respond(status, json.dumps(data, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= MAX_BODY:
            raise ValueError('Arquivo/requisição muito grande ou vazia (máximo 15 MB).')
        return self.rfile.read(length)

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path == '/':
                self.respond(200, (ROOT/'static'/'index.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/api/config':
                self.json(200, load_config())
            elif path in ('/preview.svg', '/preview-light.svg'):
                self.respond(200, render_svg(load_config(), light=path.endswith('light.svg')), 'image/svg+xml; charset=utf-8')
            elif path in ('/download/dark_mode.svg', '/download/light_mode.svg'):
                self.respond(200, render_svg(load_config(), light='light' in path), 'image/svg+xml; charset=utf-8', {'Content-Disposition':f'attachment; filename="{path.rsplit("/",1)[-1]}"'})
            else:
                self.json(404, {'error':'Não encontrado'})
        except Exception as e:
            self.json(400, {'error':str(e)})

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path == '/api/photo':
                payload = self.body()
                # Image decoding validates actual content, not the claimed extension.
                with Image.open(io.BytesIO(payload)) as image:
                    if image.width * image.height > 25_000_000:
                        raise ValueError('Foto muito grande (até 25 megapixels).')
                    im = ImageOps.exif_transpose(image).convert('RGBA')
                im.thumbnail((1800,1800), Image.Resampling.LANCZOS)
                target = ROOT/'assets'/'retrato.png'
                im.save(target, optimize=True)
                config = load_config()
                config['profile']['photo'] = 'assets/retrato.png'
                DEFAULT_CONFIG.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
                self.json(200, {'ok':True,'path':'assets/retrato.png'})
            elif path in ('/api/render','/api/save'):
                raw = json.loads(self.body())
                config = normalize_config(raw)
                if path == '/api/render':
                    self.respond(200, render_svg(config, light=bool(raw.get('preview_light', False))), 'image/svg+xml; charset=utf-8')
                else:
                    # Only the app's fixed project config is ever written.
                    DEFAULT_CONFIG.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
                    files = generate(config)
                    self.json(200, {'ok':True,'files':[str(f.relative_to(ROOT)) for f in files]})
            elif path == '/api/stats':
                raw = json.loads(self.body())
                username = str(raw.get('username','')).strip()
                if not username or not all(c.isalnum() or c == '-' for c in username) or len(username) > 39:
                    raise ValueError('Digite um usuário válido do GitHub.')
                def github(endpoint):
                    req = Request('https://api.github.com/'+endpoint, headers={'Accept':'application/vnd.github+json','User-Agent':'ASCII-Profile-Studio'})
                    with urlopen(req, timeout=8) as response:
                        return json.load(response)
                user = github(f'users/{username}')
                # Up to 100 repos per page. API allows 100 pages, but this optional
                # quick button deliberately returns basic public counts only.
                self.json(200, {'repositories':user.get('public_repos',0), 'followers':user.get('followers',0), 'profile_url':user.get('html_url','')})
            else:
                self.json(404, {'error':'Não encontrado'})
        except Exception as e:
            self.json(400, {'error':str(e)})


def main():
    parser = argparse.ArgumentParser(description='Editor local de README ASCII')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=8765, type=int)
    parser.add_argument('--generate', action='store_true', help='Gerar SVG sem abrir o servidor')
    opts = parser.parse_args()
    if opts.generate:
        for path in generate(load_config()): print(path)
        return
    server = ThreadingHTTPServer((opts.host, opts.port), Handler)
    print(f'Editor pronto em http://{opts.host}:{opts.port} (Ctrl+C para sair)', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__':
    main()
