from __future__ import annotations

import hashlib
import hmac
import time


PHASE1_CONNECTOR_BASE_PATH = "/wp-json/trendplot/v1"


def build_signature_string(*, method: str, path: str, timestamp: str, body: str) -> str:
    return f"{method.upper()}\n{path}\n{timestamp}\n{body}"


def sign_request(
    *,
    method: str,
    path: str,
    body: str,
    shared_secret: str,
    timestamp: str | None = None,
) -> tuple[str, str]:
    ts = timestamp or str(int(time.time()))
    signature_string = build_signature_string(method=method, path=path, timestamp=ts, body=body)
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        signature_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return ts, signature


def connector_auth_headers(
    *,
    method: str,
    path: str,
    body: str,
    site_id: str,
    shared_secret: str,
    timestamp: str | None = None,
) -> dict[str, str]:
    ts, signature = sign_request(
        method=method,
        path=path,
        body=body,
        shared_secret=shared_secret,
        timestamp=timestamp,
    )
    return {
        "X-Trendplot-Site-Id": site_id,
        "X-Trendplot-Timestamp": ts,
        "X-Trendplot-Signature": signature,
        "Accept": "application/json",
    }
