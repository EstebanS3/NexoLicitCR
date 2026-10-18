"""Caída física de un worker y fencing con MongoDB real (NLC-05). Opt-in; no borra bases."""

import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from nexolicitcr.config import Settings
from nexolicitcr.jobs import JobQueue, LeaseLost, execute
from nexolicitcr.matching import deadline_status
from nexolicitcr.sicop import normalize
from nexolicitcr.storage import Store, connect, utcnow

ROOT = Path(__file__).resolve().parents[1]
CATEGORY = "obras"
LEASE = 15  # Mínimo permitido por la configuración.

sys.path.insert(0, str(Path(__file__).parent))
from worker_crash_helper import Source, parts  # noqa: E402


@pytest.fixture
def real():
    local = os.getenv("NEXO_TEST_LOCAL") == "1"
    atlas = os.getenv("NEXO_TEST_ATLAS") == "1"
    if not local and not atlas:
        pytest.skip("Opt in with NEXO_TEST_LOCAL=1 or NEXO_TEST_ATLAS=1")
    if local and atlas:
        pytest.fail("Select only one MongoDB integration environment")
    database_name = os.environ.get("NEXO_TEST_DATABASE", "")
    if not database_name.startswith("nexolicit_test_"):
        pytest.fail("NEXO_TEST_DATABASE must start with nexolicit_test_")
    cfg = Settings()
    if cfg.mongo_mode != ("local" if local else "atlas"):
        pytest.fail("Integration opt-in does not match MONGO_MODE")
    cfg = cfg.model_copy(
        update={"installation_id": f"crash-{uuid4().hex[:12]}", "job_lease_seconds": LEASE}
    )
    with connect(cfg) as client:
        store = Store(client[database_name])
        store.ensure_indexes()
        foreign = [
            row["_id"]
            for row in store.db.tenders.find({"payload.category": CATEGORY})
            if deadline_status(row["payload"]) not in {"closed", "canceled"}
        ]
        if foreign:
            # El worker revisita activos de la base; datos ajenos alterarían el recorrido.
            pytest.fail(f"La base de prueba ya tiene concursos activos de {CATEGORY}")
        created = []
        try:
            yield cfg, client, store, JobQueue(store, cfg), created
        finally:
            keys = [f"{cartel_no}:00" for cartel_no in created]
            store.db.tenders.delete_many({"_id": {"$in": keys}})
            store.db.tender_versions.delete_many({"key": {"$in": keys}})
            jobs = [
                row["_id"] for row in store.db.jobs.find({"installation_id": cfg.installation_id})
            ]
            store.db.sync_runs.delete_many({"_id": {"$in": jobs}})
            store.db.jobs.delete_many({"installation_id": cfg.installation_id})


def ids(created, count):
    new = [str(uuid4().int)[:20] for _ in range(count)]
    created.extend(new)
    return new


def wait_for(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.25)
    pytest.fail(message)


@pytest.mark.integration
def test_killed_worker_is_recovered_by_lease_without_repeating_work(real, tmp_path):
    cfg, _client, store, queue, created = real
    first, second = ids(created, 2)
    job = queue.enqueue(CATEGORY, 2, "", f"crash-{uuid4().hex}")
    marker = tmp_path / "victim.marker"
    env = dict(
        os.environ,
        INSTALLATION_ID=cfg.installation_id,
        JOB_LEASE_SECONDS=str(LEASE),
        PYTHONUTF8="1",
    )
    victim = subprocess.Popen(  # noqa: S603 - intérprete y script propios de la prueba
        [
            sys.executable,
            str(Path(__file__).parent / "worker_crash_helper.py"),
            job["_id"],
            str(marker),
            f"{first},{second}",
            second,
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        wait_for(
            lambda: marker.exists() or victim.poll() is not None,
            90,
            "El worker víctima no llegó al segundo concurso",
        )
        if victim.poll() is not None:
            pytest.fail(f"El worker terminó solo: {victim.stderr.read().decode()[-2000:]}")
        victim.kill()  # Caída física: sin finally, sin finish, sin liberar el lease.
        victim.wait(timeout=30)
    finally:
        if victim.poll() is None:
            victim.kill()

    crashed = queue.get(job["_id"])
    assert crashed["status"] == "running" and crashed["owner"] == "victim"
    assert crashed["attempt"] == 1
    assert crashed["checkpoint"] == [f"{CATEGORY}:{first}:00"]
    assert store.tender(f"{first}:00") is not None
    assert store.tender(f"{second}:00") is None

    # Un lease vigente no se reclama aunque el dueño ya no exista.
    if crashed["lease_until"] > utcnow():
        assert queue.claim("rescuer", job["_id"]) is None
    wait_for(
        lambda: queue.get(job["_id"])["lease_until"] < utcnow(),
        LEASE * 3,
        "El lease del worker caído no venció",
    )

    rescued = queue.claim("rescuer", job["_id"])
    assert rescued is not None, "El lease vencido no se recuperó"
    assert rescued["attempt"] == 2 and rescued["lease_token"] != crashed["lease_token"]
    assert rescued["checkpoint"] == crashed["checkpoint"]

    source = Source([first, second])
    result = execute(queue, rescued, source=source)
    assert result["status"] == "succeeded"
    assert source.fetched == [second], "Se repitió trabajo ya confirmado"
    assert sorted(result["checkpoint"]) == sorted(
        f"{CATEGORY}:{cartel_no}:00" for cartel_no in (first, second)
    )
    assert store.db.tender_versions.count_documents({"key": f"{first}:00"}) == 1
    # El token del worker muerto ya no confirma nada.
    with pytest.raises(LeaseLost):
        queue.finish(crashed, "failed")
    assert queue.get(job["_id"])["status"] == "succeeded"


@pytest.mark.integration
def test_expired_worker_cannot_commit_results(real):
    _cfg, client, store, queue, created = real
    (cartel_no,) = ids(created, 1)
    queue.enqueue(CATEGORY, 1, "", f"fence-{uuid4().hex}")
    stale = queue.claim("stale")
    store.db.jobs.update_one({"_id": stale["_id"]}, {"$set": {"lease_until": utcnow()}})
    current = queue.claim("current")
    assert current and current["lease_token"] != stale["lease_token"]

    listing, detail, lines = parts(cartel_no)
    tender = normalize(listing, detail, lines, CATEGORY)
    with pytest.raises(LeaseLost):
        store.save_tender(tender, utcnow(), fence=lambda session: queue.guard(stale, session))
    assert store.tender(tender.key) is None
    assert store.db.tender_versions.count_documents({"key": tender.key}) == 0

    # Aunque escriba antes de la barrera, la transacción real se revierte completa.
    probe = f"{cartel_no}:00"

    def write_then_fence(session):
        store.db.tenders.insert_one({"_id": probe, "payload": {}}, session=session)
        queue.guard(stale, session)

    with client.start_session() as session:
        with pytest.raises(LeaseLost):
            session.with_transaction(write_then_fence)
    assert store.db.tenders.find_one({"_id": probe}) is None

    with pytest.raises(LeaseLost):
        queue.checkpoint(stale, f"{CATEGORY}:{cartel_no}:00")
    with pytest.raises(LeaseLost):
        queue.finish(stale, "succeeded")

    # El dueño vigente sí confirma, con la misma barrera dentro de la transacción.
    fence_before = queue.get(current["_id"]).get("fence", 0)
    assert (
        store.save_tender(tender, utcnow(), fence=lambda session: queue.guard(current, session))
        == "changed"
    )
    assert queue.get(current["_id"])["fence"] == fence_before + 1
    queue.checkpoint(current, f"{CATEGORY}:{cartel_no}:00")
    queue.finish(current, "succeeded")
    finished = queue.get(current["_id"])
    assert finished["status"] == "succeeded" and finished["progress"] == 1
