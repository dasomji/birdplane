"""Isolated L2 migration + boot + database-refusal check (inside test image)."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

subprocess.run(["python", "manage.py", "migrate", "--noinput"], check=True)
subprocess.run(["python", "manage.py", "migrate", "--check"], check=True)
server = subprocess.Popen(
    ["python", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"]
)
try:
    for attempt in range(60):
        if server.poll() is not None:
            raise RuntimeError("API exited before health success")
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/", timeout=2
            ) as response:
                assert response.status == 200
                assert json.load(response)["status"] == "OK"
            break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    else:
        raise RuntimeError("API health timed out")
    print("API migrated and booted: health success", flush=True)
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)

refused = subprocess.run(
    ["python", "manage.py", "migrate", "--check"],
    env={**os.environ, "DATABASE_URL": "postgresql://plane:plane@127.0.0.1:1/plane"},
    check=False,
    capture_output=True,
    text=True,
    timeout=30,
)
assert refused.returncode != 0, (
    "Migrations unexpectedly accepted an unreachable database"
)
assert "connection refused" in refused.stderr.lower(), refused.stderr
print(
    "API failure case: unreachable database refused; migration exited nonzero",
    flush=True,
)
