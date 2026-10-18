"""Offline microbenchmark. Does not claim MongoDB/Redis network or OCR latency."""

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from nexolicitcr.cache import OptionalCache
from nexolicitcr.config import Settings
from nexolicitcr.matching import score
from nexolicitcr.models import CatalogItem
from nexolicitcr.sicop import normalize


class MemoryCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.values[key] = value


def measure(action, samples):
    times = []
    result = None
    for _ in range(samples):
        start = time.perf_counter()
        result = action()
        times.append((time.perf_counter() - start) * 1000)
    return result, {
        "samples": samples,
        "p50_ms": round(statistics.median(times), 3),
        "p95_ms": round(sorted(times)[math.ceil(len(times) * 0.95) - 1], 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument(
        "--counts",
        nargs="+",
        type=int,
        default=[100, 1000],
        help="Tamaños; 100/1.000 para la entrega académica, 10.000 como ampliación.",
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/matching-benchmark.json"))
    args = parser.parse_args()
    if not 3 <= args.samples <= 100:
        parser.error("samples must be 3..100")
    if any(not 1 <= count <= 10000 for count in args.counts):
        parser.error("counts must be 1..10000")
    data = json.loads(Path("tests/fixtures/tender.json").read_text())
    tender = normalize(data["listing"], data["detail"], data["lines"], "servicios").model_dump(
        mode="json"
    )
    catalog = {
        "items": [
            CatalogItem(name="Soporte", keywords=["soporte", "redes"]).model_dump() | {"id": "item"}
        ]
    }
    cfg = Settings(
        _env_file=None,
        atlas_uri="mongodb+srv://cluster.example.mongodb.net/",
        atlas_usuario="fixture",
        atlas_clave="fixture-only",
    )
    measurements = []
    for count in dict.fromkeys(args.counts):
        cache = OptionalCache(cfg, MemoryCache())
        key = cache.key("benchmark", 1, 1, "v1", {"count": count})

        def calculate(count=count):
            return [{"key": str(i), "match": score(tender, catalog)} for i in range(count)]

        rows, cold = measure(calculate, args.samples)
        cache.put(key, rows)
        cached, warm = measure(lambda cache=cache, key=key: cache.get(key), args.samples)
        # Oversize snapshots intentionally bypass cache; report that separately.
        measurements.append(
            {
                "tenders": count,
                "catalog_items": 1,
                "uncached": cold,
                "memory_cache_read": warm if cached is not None else None,
                "cache_stored": cached is not None,
                "equivalent": cached == rows if cached is not None else None,
                "json_bytes": len(
                    json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()
                ),
            }
        )
    report = {
        "kind": "offline_matching_microbenchmark",
        "limitations": [
            "synthetic data",
            "one catalog item",
            "in-memory Redis double",
            "no MongoDB I/O",
            "no HTTP or OCR",
            "p95 is descriptive with few samples",
        ],
        "results": measurements,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
