from typer.testing import CliRunner

from nexolicitcr.cli import app
from nexolicitcr.jobs import JobQueue


def test_worker_once_reports_failed_attempt(store, settings, monkeypatch):
    monkeypatch.setattr("nexolicitcr.cli.db_action", lambda action: action(store, settings))
    queue = JobQueue(store, settings)
    queue.enqueue("bienes", 1, "", "cli-status")
    monkeypatch.setattr("nexolicitcr.jobs.execute", lambda queue, job: {"status": "failed"})
    assert CliRunner().invoke(app, ["worker", "--once"]).exit_code == 1


def test_sync_once_and_enqueue_share_jobs(store, settings, monkeypatch):
    monkeypatch.setattr("nexolicitcr.cli.db_action", lambda action: action(store, settings))
    monkeypatch.setattr("nexolicitcr.jobs.execute", lambda queue, job: {"status": "succeeded"})
    result = CliRunner().invoke(app, ["sync", "--category", "bienes", "--limit", "1", "--once"])
    assert result.exit_code == 0 and "succeeded" in result.stdout
    assert store.db.jobs.count_documents({}) == 1
    assert CliRunner().invoke(app, ["sync", "--category", "invalid"]).exit_code != 0


def test_api_owns_worker_only_in_local_mode(store, settings, monkeypatch):
    from contextlib import contextmanager

    events = []

    @contextmanager
    def worker_context():
        events.append("start")
        try:
            yield
        finally:
            events.append("stop")

    monkeypatch.setattr("nexolicitcr.cli.settings", lambda: settings)
    from fastapi.testclient import TestClient

    from nexolicitcr.web import create_app

    monkeypatch.setattr("nexolicitcr.web.local_worker", worker_context)
    monkeypatch.setattr(
        "nexolicitcr.web.create_app",
        lambda cfg, **kwargs: create_app(cfg, store, **kwargs),
    )

    def serve(application, **kwargs):
        with TestClient(application):
            events.append("web")
            raise RuntimeError("server stopped")

    monkeypatch.setattr("uvicorn.run", serve)
    assert CliRunner().invoke(app, ["api"]).exit_code != 0
    assert events == ["start", "web", "stop"]
    events.clear()
    CliRunner().invoke(app, ["api", "--no-worker"])
    assert events == ["web"]
    events.clear()
    settings.app_mode = "server"
    CliRunner().invoke(app, ["api"])
    assert events == ["web"]


def test_worker_recovers_after_mongo_outage(store, settings, monkeypatch):
    from pymongo.errors import AutoReconnect

    monkeypatch.setattr("nexolicitcr.cli.db_action", lambda action: action(store, settings))
    events = []

    def claim(self, owner):
        events.append("claim")
        if events.count("claim") == 1:
            raise AutoReconnect("temporary outage")
        raise KeyboardInterrupt()

    monkeypatch.setattr(JobQueue, "claim", claim)
    monkeypatch.setattr("time.sleep", lambda seconds: events.append("wait"))
    assert CliRunner().invoke(app, ["worker"]).exit_code == 0
    assert events == ["claim", "wait", "claim"]
