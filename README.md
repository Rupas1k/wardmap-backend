# dota2wardmap backend

## Structure

```text
dota2wardmap/
├── api/             # Flask HTTP blueprints
├── clustering/      # Pandas/HDBSCAN service and worker
├── integrations/    # External API clients
├── replay/          # League collection, replay parsing, persistence, and worker
├── jobs.py          # Durable PostgreSQL job claiming and retry state
├── models.py        # Application and job models
├── extensions.py    # Shared SQLAlchemy, migration, and Redis clients
└── migrations/      # Alembic schema migrations
```

The API and workers use the same image with different entry points. PostgreSQL
is authoritative for application data and jobs; Redis contains only rebuildable
cluster caches.

## Run locally

The backend repository is self-contained. Copy the example environment once,
review its values, and start the complete stack from this directory:

```bash
cp .env-example .env
docker compose up -d --build
```

Compose automatically reads this repository's `.env`. It starts PostgreSQL,
Redis, migrations, the Flask API, match collector, replay parser children, and
clustering worker. The API is available at `http://localhost:5000`.

Operational commands:

```bash
docker compose ps -a
docker compose logs -f
docker compose logs -f match-collector replay-worker cluster-worker
docker compose down
```

PostgreSQL is exposed at `localhost:5432` and Redis at `localhost:6379`; both
ports are bound to localhost. Application/job data and cache data use named
Docker volumes and survive `docker compose down`.

The replay service uses `PARSER_WORKERS` named native parser child processes.
Its logs identify each child, for example `replay-parser-2`.

The collector checks PostgreSQL every `COLLECTOR_INTERVAL_SECONDS` and calls
OpenDota only when an active league's `next_check_at` is due. It adds unseen completed matches as durable replay jobs
and backs off from 15 minutes to one hour and then six hours when repeated
checks find nothing new. The replay worker queues server-side observer and
sentry cluster compilation after parsing.
Cluster compilation is debounced by `CLUSTER_BATCH_DELAY_SECONDS` (30 seconds
by default), so a burst of parsed replays produces one rebuild per league and
ward type after parsing becomes quiet. `CLUSTER_BATCH_MAX_WAIT_SECONDS` (120
seconds by default) forces a rebuild during continuous parsing so a busy import
cannot postpone clustering indefinitely.

Clustering runs in a separate worker so the API does not load or execute
Pandas/scikit-learn.

`POST /api/v1/clusters` adds a durable PostgreSQL job and returns `202`;
`GET /api/v1/leagues/<league_id>/clusters/<observer|sentry>` returns the last
completed clustering result from Redis.

Replay and clustering jobs use PostgreSQL so claimed work can be retried after
a worker failure. Redis is used only for completed cluster caches.
Completed and permanently failed queue records are retained for
`JOB_RETENTION_DAYS` and then deleted in bounded batches by the collector.

`POST /api/v1/wards/query` uses cursor pagination with a page-size ceiling
determined by the caller's access level. Health probes are available at
`/health/live` and `/health/ready`.

## API access

Read endpoints support anonymous access. Advanced and administrator access use
unique revocable API keys sent as `Authorization: Bearer <key>`. Keys are shown
only once when created; PostgreSQL stores their SHA-256 hashes, not the raw
values.

Create one key per user or service:

```bash
docker compose exec api flask --app dota2wardmap:create_app keys create \
  --owner "user@example.com" --access advanced

docker compose exec api flask --app dota2wardmap:create_app keys create \
  --owner "operations" --access admin
```

List key prefixes and revoke a key without knowing its raw value:

```bash
docker compose exec api flask --app dota2wardmap:create_app keys list
docker compose exec api flask --app dota2wardmap:create_app keys revoke wm_example
```

Revocation takes effect on the next request. Create a replacement before
revoking an active key when rotating credentials.

Default policy:

- Anonymous: 60 requests/minute and at most 1,000 wards per page.
- Advanced: 600 requests/minute and at most 5,000 wards per page.
- Admin: no general rate limit and at most 10,000 wards per page.
- League collection and manually queued clustering require admin access.

All limits are configurable through the corresponding values in
`.env-example`. `GET /api/v1/auth/me` returns the access level associated with
the current request. The browser UI stores a supplied key in `sessionStorage`,
so it is cleared when the browser session ends; avoid entering keys on an
untrusted device.

## Application image

Build the production image, including the native Rust parser:

```bash
docker build --tag dota2wardmap-back .
```

### Helper scripts

The same workflow is available through scripts that can be called from any
working directory:

```bash
./scripts/services-up.sh
./scripts/build.sh
./scripts/migrate.sh
./scripts/run.sh
```

Stop the Compose services with:

```bash
./scripts/services-down.sh
```

`IMAGE_NAME=my-image ./scripts/build.sh` overrides the default image name.
Arguments passed to `run.sh` replace the image's default Gunicorn command; for
example, `./scripts/run.sh flask --app dota2wardmap:create_app routes`.

## External dependencies

League metadata, completed league matches, match participants, and replay
metadata come from OpenDota. The public API works without credentials. Set the
optional `OPENDOTA_API_KEY` in `.env` when higher API limits are needed.

`POST /api/v1/leagues/<league_id>/queue` queues completed matches returned by
OpenDota. Live
match discovery is intentionally not part of the application. Players are
learned from each completed match while its replay is processed because
OpenDota does not provide a canonical historical league-roster endpoint.

League collection status is `active`, `paused`, or `completed`. Since OpenDota
does not expose an authoritative tournament end state, an administrator changes
that state explicitly:

```bash
curl --request POST \
  --header "Authorization: Bearer $WARDMAP_ADMIN_KEY" \
  --header "Content-Type: application/json" \
  --data '{"status":"completed"}' \
  http://localhost:5000/api/v1/leagues/19892/tracking
```

Resuming with `{"status":"active"}` schedules an immediate collection check.
The league table also owns map asset version, OpenDota tier, observed first and
last match times, collection schedule, and completion metadata.

Player participation is stored once in `players_matches`. League participation
is derived through each match's `league_id`; there is intentionally no duplicate
`players_leagues` table. Cluster output remains rebuildable Redis data, so there
is no write-only maps or cluster-artifact table.

The replay parser is the Rust/PyO3 project in `./replay_parser`. It is a local
dependency in `requirements.txt`, so Maturin builds and installs it with the
rest of the Python environment:

```bash
pip install -r requirements.txt
```

`dota2wardmap/models.py` defines the current schema, while Alembic migrations
under `dota2wardmap/migrations` define how existing databases reach it. Apply
pending migrations before starting the application:

```bash
flask --app dota2wardmap:create_app db upgrade
flask --app dota2wardmap:create_app run
```
