"""
Can this machine reach WhoScored at all?

Written because the scheduled job started failing every run and the logs are
admin-only, while step names and their conclusions are public. The verdict is
written to GITHUB_OUTPUT so the workflow can light up one of three
differently-named steps, which makes the answer readable from the REST API by
anyone -- including from a session that cannot download the logs.

This asks one question and nothing else: a single request, no retries, no
parsing. If it comes back 200 the runner can reach WhoScored and the fetch
failure is ours; if it comes back 403 or 429 the address is being refused and
no amount of application code fixes it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import http  # noqa: E402

URL = "https://www.whoscored.com/Regions/252/Tournaments/2"


def main() -> int:
    verdict, detail = "other", ""
    try:
        session = http.session()
        response = session.get(URL, timeout=25)
        status = response.status_code
        detail = f"HTTP {status}, {len(response.content)} bytes"
        if status == 200:
            verdict = "ok"
        elif status in (403, 429):
            verdict = "refused"
    except Exception as exc:
        detail = f"{type(exc).__name__}: {str(exc)[:160]}"

    print(f"verdict={verdict} ({detail})")
    print(f"proxy: {http.proxy_status()}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(f"verdict={verdict}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
