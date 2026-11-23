# PinPoint

**A personalized recommendation pipeline built with Python, C, Java, and SQLite.**

PinPoint turns saved-item feedback into an explainable discovery feed. Python builds TF-IDF interest profiles, a native C library computes cosine similarity and selects top-k candidates, and a Java REST API serves recommendations and records feedback.

The project includes a Pinterest-inspired interface, a Python reference implementation, cross-language correctness tests, and reproducible performance and offline evaluation reports.

![PinPoint discovery feed](reports/preview.jpg)

## Capabilities

- Personalized recommendations from saved-item feedback, with shared-tag explanations.
- Idempotent save/unsave events persisted in SQLite and isolated by demo profile.
- Exclusion of saved items and a popularity fallback for profiles without feedback.
- Equivalent C and Python ranking engines with deterministic tie-breaking.
- An image-based masonry feed with topic filters, search, saved collections, and item details.

The sample catalog contains 48 original synthetic items across six categories. Bundled photographs illustrate the catalog; recommendations use tags, not image pixels. This is a content-based recommender, not an LLM or an image-understanding model.

## Quick start

### Requirements

- Python 3.10 or later
- JDK 17 or later (`java` and `javac` on PATH)
- A C11 compiler available as `cc`
- macOS or Linux; use WSL on Windows

No third-party Python packages, Java dependencies, or API keys are required.

```sh
git clone https://github.com/abhijeethasvin-sudo/pinpoint-recommender.git
cd pinpoint-recommender
python3 build.py
python3 run.py
```

Open **http://127.0.0.1:8080**. If the port is occupied, use `python3 run.py --port 8081`. Stop the server with Ctrl+C.

In VS Code, **Terminal → Run Task → PinPoint: Run API and demo** builds and launches the application. Build, test, benchmark, and evaluation tasks are also included.

### Try the feedback loop

1. Open **Explore** and save two ideas from a topic you like.
2. Open **Home** to see unsaved items ranked around those interests.
3. Open an item to inspect its shared-interest explanation.
4. Open the profile avatar to select the Python reference engine or load a different demo profile.

Saving an item creates a backend `like` event; unsaving removes that signal. The local database persists across server restarts.

## Architecture

```text
Browser / REST client
        |
        v
Java HTTP service
  routes · validation · concurrency limit · process timeout
        |
        v
Python recommendation service
  catalog · SQLite feedback · TF-IDF vectors · interest profile
        |
        +-----------------------------+
        |                             |
        v                             v
C shared library via ctypes      Python reference
cosine scores + top-k heap        equivalent ranking
        |                             |
        +-------------+---------------+
                      |
                      v
          Shared-tag explanations → JSON response
```

| Component | Responsibility |
|---|---|
| Java | HTTP routes, JSON responses, static assets, bounded subprocess execution |
| Python | Feature construction, personalization, feedback storage, explanations, evaluation |
| C | Dense-vector scoring and bounded-heap top-k selection |
| SQLite | Persistent `(user, item)` feedback with a uniqueness constraint |
| Browser | Discovery feed, local text/topic filters, save actions, item details |

Java starts a Python subprocess for each pipeline request. Python loads the C library directly through `ctypes`; C is not invoked as a separate executable. This boundary keeps responsibilities explicit and easy to inspect, at the cost of process startup and repeated feature preparation.

## Ranking model

1. Construct a vocabulary from catalog tags.
2. Weight each item's tags using `idf(t) = log((N + 1) / (df(t) + 1)) + 1`.
3. L2-normalize the item vectors.
4. Sum vectors for a profile's saved items and L2-normalize the result.
5. Exclude saved items, score the remaining candidates, and return top-k results.

For normalized vectors, cosine similarity is their dot product. The C implementation retains the best k candidates in a worst-first heap, then sorts the retained results. Exact score ties favor the lower item ID.

For N candidates, D dimensions, and k results:

- **Time:** `O(ND + N log k + k log k)`
- **Additional ranking space:** `O(k)`, excluding input buffers

A profile without feedback receives a local-popularity fallback. If there are no popularity signals, item ID provides deterministic ordering. Shared tags explain matches; scores are similarities, not calibrated probabilities.

## API

Base URL: `http://127.0.0.1:8080`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Java service liveness |
| GET | `/api/items?user=demo` | Catalog and saved item IDs |
| POST | `/api/likes` | Record an idempotent like |
| DELETE | `/api/likes` | Remove a like |
| GET | `/api/recommendations?user=demo&k=8&engine=c` | Ranked recommendations or cold-start fallback |

Mutation bodies use `application/x-www-form-urlencoded`:

```sh
curl -X POST http://127.0.0.1:8080/api/likes \
  -d 'user=demo&item=9'

curl 'http://127.0.0.1:8080/api/recommendations?user=demo&k=5&engine=c'

curl -X DELETE http://127.0.0.1:8080/api/likes \
  -d 'user=demo&item=9'
```

`engine` accepts `c` or `python`; `k` accepts 1–50. Profile identifiers accept 1–40 letters, digits, underscores, or hyphens. Invalid inputs return 400, unknown items return 404, worker saturation returns 429, and pipeline timeouts return 504.

The Java service permits four active pipeline workers and enforces a 15-second subprocess timeout. SQL statements use parameters, process arguments bypass the shell, and the server binds to loopback. The health endpoint checks Java liveness, not every downstream component.

`pipeline_ms` measures work inside Python. It excludes Python startup, Java overhead, HTTP transport, and rendering. Java logs its handler elapsed time separately.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

The current suite contains **27 passing tests**, covering:

- Randomized C/Python score and ranking equivalence, including negative vectors and ties.
- Empty candidates, zero profiles, invalid dimensions, and non-finite inputs.
- Cold start, saved-item exclusion, user isolation, idempotency, and persistence.
- Real HTTP requests through Java → Python → C using an isolated temporary database.
- API validation, origin checks, static content, and bundled image delivery.

See [verification notes](reports/VERIFICATION.md) for the manual browser checks and their limits.

## Performance

```sh
python3 benchmark.py
```

The benchmark compares equivalent dense-vector cosine scoring and bounded top-k selection. Both engines receive the same normalized vectors and are checked for equivalent rankings and scores.

Example results for **10,000 items × 48 dimensions, k=10**, measured on an arm64 Mac with Python 3.10.11 and Apple Clang 21 (`-O3`, without fast-math):

| Measurement | Python median | C median | Python / C |
|---|---:|---:|---:|
| Query against a prepared index | 15.2493 ms | 0.0960 ms | 158.85× |
| Build index buffers and run one query | 31.0860 ms | 41.6693 ms | 0.75× |

Measurements use seven repeats after a warmup. Prepared-query timing excludes index construction for both engines and includes the C call boundary and result conversion. Build-and-query timing includes validation and native buffer packing.

**The prepared C ranking kernel is faster on this workload, but constructing fresh native buffers outweighs that gain.** The current API rebuilds those buffers per request, so the kernel speedup is not an API-level speedup.

Full results, methodology, and raw measurements: [benchmark report](reports/BENCHMARK.md) · [JSON](reports/benchmark.json).

## Offline evaluation

```sh
python3 evaluate.py
```

The evaluation uses 36 synthetic profiles, each with two training likes and two held-out likes, and compares personalized recommendations with a popularity baseline. Held-out feedback is excluded from profile construction and popularity counts. Evaluation runs against a temporary database and does not alter live demo profiles.

Because interactions are generated from catalog categories, the setup favors content-based ranking. These results validate the evaluation pipeline; they do not establish real-user relevance or generalization.

Methodology and results: [evaluation report](reports/EVALUATION.md) · [JSON](reports/evaluation.json).

## Tradeoffs and next steps

- **Process and preparation overhead:** replace per-request Python startup with a persistent worker that reuses normalized vectors and native buffers; measure end-to-end HTTP latency before and after.
- **Small synthetic catalog:** evaluate a larger, independently labelled or licensed interaction dataset before making recommendation-quality claims.
- **Dense representation:** sparse features and candidate retrieval would better fit a larger vocabulary and catalog.
- **Relevance only:** add diversity constraints and evaluate their effect alongside relevance metrics.
- **Local demo scope:** profile names are not authenticated accounts. Production deployment requires authentication, authorization, quotas, operational monitoring, and load testing.

## Repository layout

```text
native/topk.c                   C scoring and heap implementation
python/ranking.py               Python reference and ctypes boundary
python/service.py               Features, personalization, and SQLite feedback
java/RecommendationServer.java   Java REST service
web/                            Discovery interface and bundled photographs
data/                           Synthetic catalog and image source URLs
tests/                          Unit and HTTP integration tests
reports/                        Measurements, evaluation, and verification
.vscode/                        Build, run, test, and debug configurations
```

## Development notes

The initial implementation was AI-assisted using Codex. The repository documents the resulting design, verification, measured limitations, and areas for further work. Contribution and interview-preparation notes are in [OWNERSHIP.md](OWNERSHIP.md).

PinPoint is an independent portfolio project and is not affiliated with Pinterest or Google. Image source URLs are recorded in [data/image-sources.json](data/image-sources.json).
