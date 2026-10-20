"""Ciclo real del worker que pertenece a la API local (POSIX, MongoDB opt-in)."""

import os
import shutil
import signal
import subprocess
import sys
import time

import httpx
import pytest
from test_restart_integration import ROOT, real  # noqa: F401 - fixture con base aislada


def wait_until(check, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.2)
    pytest.fail("El proceso no alcanzó el estado esperado")


def workers(parent):
    rows = subprocess.check_output(  # noqa: S603 - argv fijo, sin shell
        [shutil.which("ps") or "/bin/ps", "-axo", "pid=,ppid=,command="], text=True
    )
    return {
        int(parts[0])
        for row in rows.splitlines()
        if len(parts := row.split(None, 2)) == 3
        and int(parts[1]) == parent
        and "nexolicitcr.cli worker" in parts[2]
    }


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.integration
@pytest.mark.skipif(os.name != "posix", reason="Demostración nativa POSIX")
def test_api_supervises_and_stops_only_its_worker(real):  # noqa: F811 - fixture importada
    port, env, _ = real
    env = dict(env, PYTHONPATH=str(ROOT / "src"), INSTALLATION_ID="runtime-owned")
    api = independent = None
    owned = set()
    try:
        independent = subprocess.Popen(  # noqa: S603 - CLI propio
            [sys.executable, "-m", "nexolicitcr.cli", "worker"],
            cwd=ROOT,
            env=dict(env, INSTALLATION_ID="runtime-independent"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        api = subprocess.Popen(  # noqa: S603 - CLI propio
            [sys.executable, "-m", "nexolicitcr.cli", "api", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def healthy():
            assert api.poll() is None
            try:
                return httpx.get(f"http://localhost:{port}/health/ready").status_code == 200
            except httpx.TransportError:
                return False

        wait_until(healthy, timeout=60)
        initial = wait_until(lambda: workers(api.pid))
        owned.update(initial)
        assert len(initial) == 1
        os.kill(next(iter(initial)), signal.SIGKILL)
        replacement = wait_until(lambda: workers(api.pid) - initial)
        owned.update(replacement)
        assert len(replacement) == 1 and healthy()
        assert independent.poll() is None

        api.terminate()
        assert api.wait(timeout=20) in {0, -signal.SIGTERM}
        wait_until(lambda: all(not alive(pid) for pid in owned))
        assert independent.poll() is None, "La API detuvo un worker ajeno"
    finally:
        for process in (api, independent):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        for pid in owned:
            if alive(pid):
                os.kill(pid, signal.SIGTERM)
