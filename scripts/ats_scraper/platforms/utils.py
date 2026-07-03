"""Shared HTTP utilities: session factory and retry logic."""

import random
import time
import requests


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)",
    "Accept": "application/json",
}


def make_session(extra_headers: dict | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if extra_headers:
        session.headers.update(extra_headers)
    return session


def retry_get(
    session: requests.Session,
    url: str,
    timeout: int = 30,
    params: dict | None = None,
) -> dict | list:
    backoff = 2
    last_exc = None
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=timeout, params=params)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff + random.uniform(0, backoff * 0.25))
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(backoff + random.uniform(0, backoff * 0.25))
            backoff *= 2
    raise RuntimeError(f"GET {url} failed after 3 retries: {last_exc}")


def retry_post(session: requests.Session, url: str, payload: dict, timeout: int = 30) -> dict | list:
    backoff = 2
    last_exc = None
    for attempt in range(3):
        try:
            resp = session.post(url, json=payload, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff + random.uniform(0, backoff * 0.25))
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(backoff + random.uniform(0, backoff * 0.25))
            backoff *= 2
    raise RuntimeError(f"POST {url} failed after 3 retries: {last_exc}")
