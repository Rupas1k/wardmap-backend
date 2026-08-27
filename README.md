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

The backend repository is self-contained. Use the project console to create the
local configuration and start the complete stack:

```bash
./wardmap init
./wardmap up
```

Compose automatically reads this repository's `.env`. It starts PostgreSQL,
Redis, migrations, the Flask API, match collector, and replay parser children.
The API is available at `http://localhost:5000`.

Common operational commands:

```bash
./wardmap status
./wardmap logs
./wardmap logs match-collector replay-worker
./wardmap health
./wardmap down
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
./wardmap keys create --owner "user@example.com" --access advanced
./wardmap keys create --owner "operations" --access admin
```

List key prefixes and revoke a key without knowing its raw value:

```bash
./wardmap keys list
./wardmap keys revoke wm_example
```

Revocation takes effect on the next request. Create a replacement before
revoking an active key when rotating credentials.

Team maintenance is available from the same console:

```bash
./wardmap backfill-match-teams --limit 500
./wardmap refresh-teams --max-age-days 30 --limit 20
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

## Project console

Run `./wardmap help` for the complete command list. The console covers setup,
Docker Compose lifecycle, logs, health checks, Flask maintenance commands,
database backups and restores, tests, container shells, and the server tunnel.
It can be called from any working directory.

```bash
./wardmap doctor
./wardmap build
./wardmap infra
./wardmap up
./wardmap restart api replay-worker
./wardmap shell api
./wardmap test
```

Use `app` for any Flask command that does not have a short alias, and `compose`
as an escape hatch for any Docker Compose operation:

```bash
./wardmap app routes
./wardmap compose top
./wardmap run flask --app dota2wardmap:create_app routes
```

Database operations are grouped under `db`:

```bash
./wardmap db current
./wardmap migrate
./wardmap db shell
./wardmap db dump backups/wardmap.dump
./wardmap db restore backups/wardmap.dump
```

Restore stops the API and workers while replacing the database, then starts
them again. It requires confirmation unless `--yes` is supplied. Backups use
PostgreSQL's portable custom format.

For laptop access to PostgreSQL and Redis on the home server, run
`./wardmap tunnel`. Override the destination with `WARDMAP_SSH_HOST` or pass an
SSH host as the first argument. The default local forwarded ports are `15432`
and `16379`.

After pushing production changes to GitHub, update both repositories and stacks
on the home server with:

```bash
./wardmap deploy
```

This invokes `/home/artemrupasov/update-wardmap` remotely. It does not replace
the local development commands or deploy uncommitted files.

The tracked implementation lives at `ops/update-wardmap`. Install it on the
server once as a stable command:

```bash
ln -sfn \
  /home/artemrupasov/projects/d2wm/dota2wardmap-back/ops/update-wardmap \
  /home/artemrupasov/update-wardmap
```

It updates both applications by default. On the server, either side can also be
updated independently:

```bash
/home/artemrupasov/update-wardmap backend
/home/artemrupasov/update-wardmap frontend
```

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
./wardmap refresh-league 19719
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
./wardmap migrate
./wardmap backfill-match-teams
./wardmap refresh-teams
```

The backfill command enriches previously parsed matches with Radiant/Dire team
identity and winner metadata from OpenDota. It is resumable; use `--limit N` to
process historical matches in batches.

Team names, tags, and logos are refreshed only when their metadata is at least
30 days old. The collector performs this stale-only check on startup; use
`refresh-teams --max-age-days N` for a manual refresh policy.
