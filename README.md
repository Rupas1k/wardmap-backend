# Wardmap backend

Backend services for [Wardmap](https://wardmap.rupasov.dev): a Flask API,
PostgreSQL-backed replay queue, OpenDota collector, native replay parser, and
background workers. Browser-side analysis and visualization live in
[`Rupas1k/wardmap`](https://github.com/Rupas1k/wardmap).

## Quick start

Requirements: Docker with Compose, Git, curl, SSH, and a POSIX shell. Clone the
repository, create the local environment, and start the complete stack:

```bash
git clone https://github.com/Rupas1k/dota2wardmap-back.git
cd dota2wardmap-back

./wardmap init
./wardmap doctor
./wardmap up
./wardmap health
```

The API is available at <http://localhost:5000>. PostgreSQL and Redis are bound
to localhost on ports `5432` and `6379`; their named volumes survive
`./wardmap down`.

For a new workstation with both repositories, follow
[Development setup](docs/development.md). For a production host, follow
[Server deployment](docs/deployment.md).

## Project console

`./wardmap` is the supported interface for local development and operations.
Run `./wardmap help` for every command.

```bash
./wardmap up                              # build and start the stack
./wardmap status                          # show every container
./wardmap logs api replay-worker          # follow selected logs
./wardmap test                            # run the local Python test suite
./wardmap migrate                         # apply pending migrations
./wardmap db dump backups/wardmap.dump    # create a database backup
./wardmap shell api                       # open a container shell
./wardmap deploy                          # update production over Tailscale
```

The `app` and `compose` commands remain escape hatches for operations without a
short alias:

```bash
./wardmap app routes
./wardmap compose top
```

## Services

| Service | Responsibility |
| --- | --- |
| `api` | Flask HTTP API and access control |
| `match-collector` | Discovers completed league matches through OpenDota |
| `replay-worker` | Downloads and parses replay jobs with native parser children |
| `migrate` | Applies Alembic migrations before application services start |
| `postgres` | Authoritative application and job data |
| `redis` | API rate limiting |

The Python application is under `dota2wardmap/`. The Rust/PyO3 parser is an
internal package under `replay_parser/` and is built into the shared backend
image.

## Maintenance commands

```bash
./wardmap refresh-league 20026
./wardmap reparse-leagues --league-id 20026
./wardmap backfill-match-teams --limit 500
./wardmap backfill-player-sides --league-id 20026
./wardmap refresh-teams --max-age-days 30 --limit 20
```

API keys are displayed once and stored as hashes:

```bash
./wardmap keys create --owner operations --access admin
./wardmap keys create --owner analyst@example.com --access advanced
./wardmap keys list
./wardmap keys revoke wm_example
```

Read endpoints permit anonymous access. Rate limits and page-size ceilings for
anonymous, advanced, and administrator access are configured in `.env` from
the documented values in `.env-example`.

## API and data model

- HTTP blueprints are mounted under `/api/v1`.
- Liveness and readiness probes are `/health/live` and `/health/ready`.
- PostgreSQL stores application data and durable replay jobs.
- Redis is not the replay queue; it is used for API rate limiting.
- Ward clustering and derived analysis are performed and cached by the browser.
- Alembic migrations under `dota2wardmap/migrations/` define schema evolution.

OpenDota supplies league metadata, completed matches, participants, and replay
metadata. `OPENDOTA_API_KEY` is optional but recommended for higher request
limits.

## Quality checks

CI runs the following on Python 3.13:

```bash
ruff check .
pyright
python -m pytest
```

Create `.venv` and install `requirements.txt`, Ruff, and Pyright to run the same
checks locally. Full instructions are in [Development setup](docs/development.md).

## Documentation

- [Development setup](docs/development.md) — new machine, both repositories,
  local services, tests, and daily workflow
- [Server deployment](docs/deployment.md) — production host, updater, restore,
  backups, Tailscale, and Cloudflare Tunnel
- [Ward analytics roadmap](docs/ward-analytics-roadmap.md)
- [Vision and observer metrics](docs/vision-observer-metrics.md)
- [Ward impact score](docs/ward-impact-score.md)
