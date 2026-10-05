"""Single-process public-demo write budgets. Not a distributed abuse-prevention layer."""
import asyncio
import os
import time
from collections import deque
from starlette.responses import JSONResponse


class DemoLimits:
    def __init__(self):
        self.max_bytes = max(1, int(os.environ.get("DEMO_MAX_REQUEST_BYTES", "16384")))
        self.per_client = max(1, int(os.environ.get("DEMO_WRITES_PER_MINUTE", "20")))
        self.global_rate = max(1, int(os.environ.get("DEMO_GLOBAL_WRITES_PER_MINUTE", "120")))
        self.max_concurrent = max(1, int(os.environ.get("DEMO_WRITE_CONCURRENCY", "2")))
        self.reset()

    def reset(self):
        self.clients = {}
        self.global_requests = deque()
        self.active = 0

    def reserve(self, client):
        # Called without awaits on the ASGI event loop; counters change atomically.
        now = time.monotonic()
        self.clients = {key: values for key, values in self.clients.items() if values and values[-1] > now - 60}
        for values in [self.global_requests, *self.clients.values()]:
            while values and values[0] <= now - 60: values.popleft()
        if client not in self.clients and len(self.clients) >= 1024:
            return "Client budget is full. Retry later."
        values = self.clients.setdefault(client, deque())
        if len(values) >= self.per_client or len(self.global_requests) >= self.global_rate:
            return "Public simulation rate limit reached. Retry later."
        if self.active >= self.max_concurrent:
            return "Public simulation is busy. Retry after the active request completes."
        values.append(now); self.global_requests.append(now); self.active += 1
        return None


class DemoLimitMiddleware:
    def __init__(self, app, limits):
        self.app, self.limits = app, limits

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        error = self.limits.reserve((scope.get("client") or ("unknown",))[0])
        if error:
            return await JSONResponse({"detail": error}, status_code=429, headers={"Retry-After": "60"})(scope, receive, send)
        try:
            headers = dict(scope.get("headers", []))
            length = headers.get(b"content-length")
            if length is not None:
                try: size = int(length)
                except ValueError: size = -1
                if size < 0: return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
                if size > self.limits.max_bytes:
                    return await JSONResponse({"detail": "Simulation request exceeds the body-size limit."}, status_code=413)(scope, receive, send)
            chunks, total = [], 0
            deadline = time.monotonic() + 10
            while True:
                try: message = await asyncio.wait_for(receive(), timeout=max(0, deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    return await JSONResponse({"detail": "Simulation request body timed out."}, status_code=408)(scope, receive, send)
                if message["type"] == "http.disconnect": return
                chunk = message.get("body", b""); total += len(chunk)
                if total > self.limits.max_bytes:
                    return await JSONResponse({"detail": "Simulation request exceeds the body-size limit."}, status_code=413)(scope, receive, send)
                chunks.append(chunk)
                if not message.get("more_body", False): break
            sent = False
            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
                return await receive()
            return await self.app(scope, replay, send)
        finally:
            self.limits.active -= 1
