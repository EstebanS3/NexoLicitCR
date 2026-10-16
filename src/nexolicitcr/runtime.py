"""Lifecycle of the optional worker owned by a local CLI web process."""

import logging
import subprocess
import sys
import threading
from contextlib import contextmanager

LOG = logging.getLogger(__name__)


@contextmanager
def local_worker():
    """Start one worker, recover unexpected exits, stop only this owned process."""
    stopped = threading.Event()

    def launch():
        return subprocess.Popen(  # noqa: S603 -- fixed module and arguments, no shell
            [sys.executable, "-m", "nexolicitcr.cli", "worker"],
            stdin=subprocess.DEVNULL,
        )

    process = launch()

    def supervise():
        nonlocal process
        delay = 2
        while not stopped.wait(1):
            if process.poll() is None:
                continue
            LOG.warning("El worker local se detuvo; reinicio en %s segundos.", delay)
            if stopped.wait(delay):
                break
            try:
                process = launch()
            except OSError:
                LOG.error("No se pudo iniciar el worker local.")
            delay = min(30, delay * 2)

    monitor = threading.Thread(target=supervise, name="local-worker-supervisor", daemon=True)
    monitor.start()
    try:
        yield
    finally:
        stopped.set()
        monitor.join()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
