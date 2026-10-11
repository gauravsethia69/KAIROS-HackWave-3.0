#!/usr/bin/env python3
"""Zero-auth public smoke checks, no Groq tokens. Only your supplied URLs."""
import argparse
import json
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def https_url(url):
    x = urlsplit(url)
    if x.scheme != 'https' or not x.netloc or x.username or x.password or x.query or x.fragment:
        raise ValueError('Use a public HTTPS origin only, without credentials/query/fragment')
    return f'https://{x.netloc}'


def check(url, expect, label):
    try:
        with urlopen(Request(url, headers={'User-Agent': 'KAIROS-Deployment-Smoke/1.0'}), timeout=14) as res:
            code, content = res.status, res.read(8192)
    except HTTPError as exc:
        code, content = exc.code, b''
    except (URLError, TimeoutError) as exc:
        print('FAIL', label, 'unreachable:', type(exc).__name__)
        return False
    ok = code == expect
    if label == 'API health' and ok:
        try:
            data = json.loads(content)
            ok = data.get('status') == 'ok' and data.get('service') == 'kairos-api'
        except (ValueError, AttributeError, TypeError):
            ok = False
    print(('PASS' if ok else 'FAIL'), label, f'HTTP {code}, expected {expect}')
    return ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--api', required=True, help='e.g. https://my-kairos-api.onrender.com')
    p.add_argument('--web', required=True, help='e.g. https://my-kairos.vercel.app')
    args = p.parse_args()
    try:
        api, web = https_url(args.api), https_url(args.web)
    except ValueError as exc:
        p.error(str(exc))
    tests = [
        (api + '/health', 200, 'API health'),
        (api + '/api/auth/me', 401, 'Anonymous authentication denied'),
        (api + '/api/intelligence/ai/usage', 401, 'Anonymous AI usage denied'),
        (api + '/api/intelligence/scheduling/options', 401, 'Anonymous scheduling denied'),
        (web + '/', 200, 'Frontend homepage'),
    ]
    results = [check(*test) for test in tests]
    ok = all(results)
    print('SMOKE PASSED (public/unauthenticated paths only)' if ok else 'SMOKE FAILED')
    print('Manual authenticated end-to-end checks still required.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
