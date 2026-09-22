"""One-time, loopback-only GitHub App manifest registration. Never prints secrets."""
import argparse
import html
import json
import os
import re
import secrets
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]


def register(worker_url, owner, port):
    parsed = urlsplit(worker_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Expected an HTTPS Worker origin')
    worker_url = worker_url.rstrip('/')
    state = secrets.token_urlsafe(32)
    binding = secrets.token_urlsafe(32)
    origin = f'http://127.0.0.1:{port}'
    config_path = ROOT / 'auth-worker/wrangler.jsonc'
    config = json.loads(config_path.read_text())
    manifest = {
        'name': 'Supply Chain Skills Lab HS',
        'url': config['vars']['SITE_URL'],
        'description': 'Personal supply-chain learning, with notes and progress saved to your selected private repository.',
        'public': True,
        'redirect_url': origin + '/callback',
        'callback_urls': [worker_url + '/auth/callback'],
        'hook_attributes': {'url': worker_url + '/unused-webhook', 'active': False},
        'default_permissions': {'contents': 'write', 'pull_requests': 'write', 'metadata': 'read'},
        'default_events': [],
        'request_oauth_on_install': False,
    }
    result = {'done': False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Callback URLs contain a one-time code. Never log request paths.

        def page(self, status, text, cookie=None):
            data = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>Supply Chain Skills Lab · 登录配置</title>'
                    '<body style="font:18px/1.8 system-ui;max-width:680px;margin:10vh auto;padding:24px">'
                    + text + '</body></html>').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action https://github.com; frame-ancestors 'none'")
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                return self.page(403, '来源不正确。')
            route = urlsplit(self.path)
            if route.path == '/start/' + state:
                payload = html.escape(json.dumps(manifest), quote=True)
                return self.page(200,
                    '<h1>完成 GitHub 登录应用配置</h1><p>Cloudflare 已连接。下一步会前往 GitHub，为这个学习网站创建登录应用。</p>'
                    '<p>请使用 <b>' + html.escape(owner) + '</b> 账号。应用只申请所选仓库的内容及 PR 读写权限；每位学习者自行选择自己的私有记录仓库。</p>'
                    '<form method="post" action="https://github.com/settings/apps/new?state=' + state + '">'
                    '<input type="hidden" name="manifest" value="' + payload + '">'
                    '<button style="font:inherit;background:#155641;color:white;border:0;border-radius:8px;padding:12px 22px">前往 GitHub 创建应用</button></form>'
                    '<p>在 GitHub 点击 Create GitHub App 后会自动返回。密钥由本机直接配置，不需要复制或发送到聊天。</p>',
                    f'scsl-setup={binding}; HttpOnly; SameSite=Lax; Path=/; Max-Age=3600')
            if route.path != '/callback':
                return self.page(404, '没有此页面。')
            query = parse_qs(route.query)
            cookie = self.headers.get('Cookie', '')
            if result['done'] or query.get('state') != [state] or f'scsl-setup={binding}' not in cookie.split('; '):
                return self.page(403, '配置请求已过期或不属于此浏览器。请返回 Codex。')
            code = query.get('code', [''])[0]
            if not re.fullmatch('[a-zA-Z0-9_-]{16,200}', code):
                return self.page(400, 'GitHub 未返回有效配置。')
            try:
                request = urllib.request.Request('https://api.github.com/app-manifests/' + code + '/conversions',
                    data=b'{}', method='POST', headers={'Accept': 'application/vnd.github+json',
                    'Content-Type': 'application/json', 'User-Agent': 'SupplyChainSkillsLab-Setup',
                    'X-GitHub-Api-Version': '2026-03-10'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    app = json.load(response)
                if app.get('owner', {}).get('login', '').lower() != owner.lower():
                    raise ValueError('Owner mismatch')
                if not app.get('client_secret') or not app.get('client_id') or not app.get('slug'):
                    raise ValueError('Missing application credentials')
                permissions = app.get('permissions', {})
                if permissions != manifest['default_permissions']:
                    raise ValueError('Unexpected permissions')
                private = ROOT / 'private'
                private.mkdir(mode=0o700, exist_ok=True)
                target = private / 'github-app-secret.json'
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    json.dump({'GITHUB_CLIENT_SECRET': app['client_secret']}, stream)
                # App private key and webhook secret are unused and are not retained.
                config['vars']['GITHUB_CLIENT_ID'] = app['client_id']
                config['vars']['GITHUB_APP_SLUG'] = app['slug']
                config_path.write_text(json.dumps(config, indent=2) + '\n')
                result['done'] = True
                print(json.dumps({'registered': True, 'slug': app['slug'], 'owner': owner,
                                  'credentials_saved_privately': True}), flush=True)
                return self.page(200, '<h1>GitHub 应用已创建</h1><p>配置已安全交给本机。现在可以回到 Codex，继续发布登录服务。</p>',
                                 'scsl-setup=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
            except Exception as error:
                # Neither upstream responses nor exception strings may disclose credentials.
                print(json.dumps({'registration_error_type': type(error).__name__}), flush=True)
                return self.page(500, '配置未完成，请回到 Codex 检查。请不要把密钥发到聊天。')

    server = HTTPServer(('127.0.0.1', port), Handler)
    server.timeout = 1
    link = origin + '/start/' + state
    print(json.dumps({'setup_url': link, 'expires_in_seconds': 3600}), flush=True)
    webbrowser.open(link)
    deadline = time.monotonic() + 3600
    while not result['done'] and time.monotonic() < deadline:
        server.handle_request()
    server.server_close()
    if not result['done']:
        raise SystemExit('Setup timed out; no login service secrets were configured.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker-url', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--port', type=int, default=8977)
    args = parser.parse_args()
    register(args.worker_url, args.owner, args.port)
