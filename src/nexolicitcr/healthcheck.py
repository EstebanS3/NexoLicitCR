"""Container readiness: query the API using its configured, trusted Host."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    origin = urlsplit(os.environ.get("PUBLIC_ORIGIN", "http://localhost:8000"))
    request = Request("http://127.0.0.1:8000/health/ready", headers={"Host": origin.netloc})
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 -- fixed loopback URL
            ready = json.load(response)
        return 0 if ready.get("mongodb") == "available" else 1
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
