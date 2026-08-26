# dota2wardmap backend

## Structure

```text
dota2wardmap/
├── api/             # Flask HTTP blueprints
├── integrations/    # External API clients
├── models/          # Gameplay, access, and job persistence models
├── replay/          # Replay download, parsing, persistence, and worker
├── jobs.py          # Durable PostgreSQL job claiming and retry state
├── extensions.py    # Shared SQLAlchemy, migration, and Redis clients
└── migrations/      # Alembic schema migrations
```

The API and replay workers use the same image with different entry points.
PostgreSQL is authoritative for application data and jobs. Ward clustering is
performed by the browser client.

## Run locally

The backend repository is self-contained. Copy the example environment once,
review its values, and start the complete stack from this directory:

```bash
cp .env-example .env
docker compose up -d --build
```

Compose automatically reads this repository's `.env`. It starts PostgreSQL,
Redis, migrations, the Flask API, match collector, and replay parser children.
The API is available at `http://localhost:5000`.

Operational commands:

```bash
docker compose ps -a
docker compose logs -f
docker compose logs -f match-collector replay-worker
docker compose down
```

PostgreSQL is exposed at `localhost:5432` and Redis at `localhost:6379`; both
ports are bound to localhost. Application/job data and cache data use named
Docker volumes and survive `docker compose down`.

### Restore PostgreSQL from a backup

The maintenance-only `db-restore` service restores the custom-format dump at
`POSTGRES_RESTORE_PATH`. The example environment points to the dated dump in
the parent project directory. Stop database clients first, run the restore,
and then start the complete stack again:

```bash
docker compose stop api match-collector replay-worker
docker compose --profile maintenance run --rm db-restore
docker compose up -d --build
```

The restore command terminates remaining connections, drops and recreates only
the database named by `POSTGRES_DB`, and then loads the dump. It does not remove
the PostgreSQL volume or the backup file. To use another backup, set an absolute
or Compose-file-relative path in `.env`, for example:

```dotenv
POSTGRES_RESTORE_PATH=/srv/backups/dota2wardmap.dump
```

The replay service uses `PARSER_WORKERS` named native parser child processes.
Its logs identify each child, for example `replay-parser-2`.

The collector checks PostgreSQL every `COLLECTOR_INTERVAL_SECONDS` and calls
OpenDota only when an active league's `next_check_at` is due. It adds unseen completed matches as durable replay jobs
and backs off from 15 minutes to one hour and then six hours when repeated
checks find nothing new. Once a replay is parsed, its ward records are
immediately available through the wards API for browser-side clustering.

Replay jobs use PostgreSQL so claimed work can be retried after a worker
failure. Redis remains in use for API access rate limiting.
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
./scripts/create-advanced-token.sh "user@example.com"
./scripts/create-admin-token.sh "operations"

# Equivalent raw commands:
docker compose exec api flask --app dota2wardmap:create_app keys create \
  --owner "user@example.com" --access advanced

docker compose exec api flask --app dota2wardmap:create_app keys create \
  --owner "operations" --access admin
```

List key prefixes and revoke a key without knowing its raw value:

```bash
./scripts/list-tokens.sh
./scripts/revoke-token.sh wm_example

# Equivalent raw commands:
docker compose exec api flask --app dota2wardmap:create_app keys list
docker compose exec api flask --app dota2wardmap:create_app keys revoke wm_example
```

Revocation takes effect on the next request. Create a replacement before
revoking an active key when rotating credentials.

Team maintenance also has shell wrappers:

```bash
./scripts/backfill-match-teams.sh --limit 500
./scripts/refresh-teams.sh --max-age-days 30 --limit 20
```

Default policy:

- Anonymous: 60 requests/minute and at most 5,000 wards per page.
- Advanced: 600 requests/minute and at most 5,000 wards per page.
- Admin: no general rate limit and at most 10,000 wards per page.
- League collection requires admin access.

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

To discover new matches and retry failed unparsed jobs for any league without
deleting successfully parsed data, run:

```bash
./scripts/refresh-league.sh 19719
```

Jobs already being processed are left untouched.

Player participation is stored once in `players_matches`. League participation
is derived through each match's `league_id`; there is intentionally no duplicate
`players_leagues` table. Cluster output is calculated and cached by the browser,
so there is no server-side cluster-artifact table.

The replay parser is the Rust/PyO3 project in `./replay_parser`. It is a local
dependency in `requirements.txt`, so Maturin builds and installs it with the
rest of the Python environment:

```bash
pip install -r requirements.txt
```

`dota2wardmap/models/` defines the current schema, while Alembic migrations
under `dota2wardmap/migrations` define how existing databases reach it. Apply
pending migrations before starting the application:

```bash
flask --app dota2wardmap:create_app db upgrade
flask --app dota2wardmap:create_app backfill-match-teams
flask --app dota2wardmap:create_app refresh-teams
flask --app dota2wardmap:create_app run
```

The backfill command enriches previously parsed matches with Radiant/Dire team
identity and winner metadata from OpenDota. It is resumable; use `--limit N` to
process historical matches in batches.

Team names, tags, and logos are refreshed only when their metadata is at least
30 days old. The collector performs this stale-only check on startup; use
`refresh-teams --max-age-days N` for a manual refresh policy.
