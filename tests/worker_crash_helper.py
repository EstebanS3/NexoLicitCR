"""Worker real para la prueba de caída física; también se ejecuta como proceso hijo."""

import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

from nexolicitcr.sicop import normalize

FIXTURE = json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())


def parts(cartel_no):
    listing, detail, lines = (deepcopy(FIXTURE[k]) for k in ("listing", "detail", "lines"))
    for record in (listing, detail, *(line["id"] for line in lines)):
        record["cartelNo"] = cartel_no
    return listing, detail, lines


class Source:
    """Fuente SICOP sintética. Puede quedarse colgada en un concurso para simular la caída."""

    def __init__(self, ids, hang_on=None, marker=None):
        self.ids, self.hang_on, self.marker = ids, hang_on, marker
        self.fetched = []

    def listings(self, category):
        for cartel_no in self.ids:
            yield parts(cartel_no)[0]

    def tender(self, listing, category, timezone=""):
        self.fetched.append(listing["cartelNo"])
        if listing["cartelNo"] == self.hang_on:
            Path(self.marker).write_text("checkpoint-persisted")
            time.sleep(3600)  # El padre termina este proceso sin limpieza.
        listing, detail, lines = parts(listing["cartelNo"])
        return normalize(listing, detail, lines, category, timezone)


def main():
    from nexolicitcr.config import Settings
    from nexolicitcr.jobs import JobQueue, execute
    from nexolicitcr.storage import Store, connect

    job_id, marker, ids, hang_on = sys.argv[1], sys.argv[2], sys.argv[3].split(","), sys.argv[4]
    settings = Settings()
    with connect(settings) as client:
        queue = JobQueue(Store(client[os.environ["NEXO_TEST_DATABASE"]]), settings)
        job = queue.claim("victim", job_id)
        if job is None:
            sys.exit(3)
        execute(queue, job, source=Source(ids, hang_on, marker))
    sys.exit(4)  # Nunca debería llegar aquí: el padre lo mata antes.


if __name__ == "__main__":
    main()
