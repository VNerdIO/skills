"""Shared HTTP and DNS helpers for the osint scripts (Python 3 standard library only)."""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CTX = ssl.create_default_context()


def fetch(url, *, data=None, headers=None, timeout=15, method=None):
    """Return (status, body_text, final_url). Never raises for HTTP errors."""
    h = {"User-Agent": UA, "Accept": "*/*", **(headers or {})}
    if isinstance(data, str):
        data = data.encode()
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read(2_000_000).decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        try:
            body = e.read(2_000_000).decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body, url
    except Exception as e:  # timeouts, DNS failures, TLS errors
        return None, f"{type(e).__name__}: {e}", url


def fetch_json(url, **kw):
    status, body, _ = fetch(url, headers={"Accept": "application/json", **kw.pop("headers", {})}, **kw)
    try:
        return status, json.loads(body)
    except ValueError:
        return status, None


def dns(name, rtype):
    """DNS over HTTPS (Cloudflare). Returns a list of answer strings."""
    q = urllib.parse.urlencode({"name": name, "type": rtype})
    _, j = fetch_json(f"https://cloudflare-dns.com/dns-query?{q}",
                      headers={"Accept": "application/dns-json"})
    return [a["data"] for a in (j or {}).get("Answer", []) if a.get("type") in RTYPES.get(rtype, ())]


RTYPES = {"A": (1,), "MX": (15,), "TXT": (16,), "PTR": (12,), "NS": (2,), "CNAME": (5,)}


def dump(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
