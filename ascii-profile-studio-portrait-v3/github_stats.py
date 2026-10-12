"""Opt-in GitHub public data retrieval. Never claims unavailable statistics."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_PATTERN = re.compile(r'(?=.{1,39}$)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$')
API = 'https://api.github.com/'


def github_get(endpoint):
    if not endpoint.startswith(('users/', 'search/')):
        raise ValueError('Endpoint não permitido.')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ASCII-Profile-Studio/2'}
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = Request(API + endpoint, headers=headers)
    try:
        with urlopen(req, timeout=12) as response:
            return json.load(response)
    except HTTPError as err:
        if err.code == 404:
            raise ValueError('Usuário GitHub não encontrado.') from err
        if err.code in (403, 429):
            raise ValueError('Limite de consultas do GitHub atingido. Aguarde ou configure GITHUB_TOKEN.') from err
        raise ValueError(f'GitHub retornou HTTP {err.code}.') from err
    except (URLError, TimeoutError) as err:
        raise ValueError('Não foi possível acessar a API do GitHub.') from err


def fetch_stats(username: str) -> dict:
    if not isinstance(username, str) or not USER_PATTERN.fullmatch(username):
        raise ValueError('Digite um nome de usuário válido do GitHub.')
    user = github_get('users/' + username)
    repos = user.get('public_repos')
    followers = user.get('followers')
    cached = {'public_repos': repos, 'followers': followers,
              'stars_received': None, 'forks_received': None,
              'contributions_year': None, 'commits_year': None}
    # Count public repos only. More than 1000 repos: intentionally mark totals
    # unavailable rather than silently reporting a partial figure.
    if isinstance(repos, int) and repos <= 1000:
        stars = forks = 0
        seen = 0
        for page in range(1, (repos + 99)//100 + 1):
            listing = github_get(f'users/{username}/repos?' + urlencode({'per_page': 100, 'page': page, 'type':'owner'}))
            if not isinstance(listing, list):
                raise ValueError('Resposta de repositórios inesperada.')
            for repo in listing:
                if not repo.get('fork', False):
                    stars += int(repo.get('stargazers_count') or 0)
                    forks += int(repo.get('forks_count') or 0)
                seen += 1
        if seen >= repos:
            cached['stars_received'] = stars
            cached['forks_received'] = forks
    return {'cached': cached, 'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'profile_url': user.get('html_url', '')}
