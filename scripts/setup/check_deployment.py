"""Real, anonymous HTTPS checks; does not log auth URLs, cookies, or credentials."""
import json
import os
import secrets
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ORIGIN = 'https://hamsterstation.github.io'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(root):
    parsed = urlsplit(root)
    assert parsed.scheme == 'https' and parsed.hostname and not parsed.username
    opener = urllib.request.build_opener(NoRedirect)

    def fetch(path, origin=ORIGIN):
        req = urllib.request.Request(root.rstrip('/') + path, headers={'Origin': origin})
        try:
            response = opener.open(req, timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read(5000)

    status, headers, data = fetch('/health')
    assert status == 200 and json.loads(data)['ready'] is True, 'Service is not configured'
    assert headers['Cache-Control'] == 'no-store'
    for path in ['/api/me', '/api/repos', '/api/state', '/api/sync', '/api/repository']:
        assert fetch(path)[0] == 401, 'Anonymous access was not rejected'
    assert fetch('/api/me', 'https://untrusted.example')[0] == 403, 'Wrong origin was not rejected'
    assert fetch('/auth/callback?state=invalid&code=invalid')[0] == 400, 'Invalid callback was not rejected'
    status, headers, _ = fetch('/auth/start?challenge=' + secrets.token_urlsafe(32))
    assert status == 302, 'Could not start login'
    target = urlsplit(headers['Location'])
    assert target.scheme == 'https' and target.netloc == 'github.com'
    assert target.path == '/login/oauth/authorize'
    assert 'HttpOnly' in headers['Set-Cookie'] and 'Secure' in headers['Set-Cookie']
    print('Real HTTPS service: ready; anonymous access blocked; origin and callback checked; GitHub login redirect works.')
    print('This does not claim a completed user login or a private-repository synchronization.')


if __name__ == '__main__':
    check(os.environ['AUTH_SERVICE_URL'])
