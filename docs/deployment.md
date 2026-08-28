# Server deployment

Wardmap production runs on `home-pc`. Docker binds application ports to
localhost, Cloudflare Tunnel publishes the web endpoints, and Tailscale
provides private SSH administration.

## Production layout

```text
/home/artemrupasov/projects/d2wm/
├── dota2wardmap-back/  # Rupas1k/wardmap-backend
└── wardmap-stage/      # Rupas1k/wardmap-stage
```

| Component | Local binding | Public endpoint |
| --- | --- | --- |
| Frontend | `127.0.0.1:4173` | `https://wardmap.rupasov.dev` |
| API | `127.0.0.1:5000` | `https://api.rupasov.dev` |
| PostgreSQL | `127.0.0.1:5432` | Not public |
| Redis | `127.0.0.1:6379` | Not public |

## Host prerequisites

Install Docker Engine with Compose, Git, Git LFS, GitHub CLI, Tailscale, and
Cloudflare Tunnel. Authenticate the deployment user rather than root:

```bash
gh auth login
gh auth setup-git
git lfs install
tailscale status
docker version
docker compose version
```

The `artemrupasov` user must be able to run Docker. Keep source checkouts,
credentials, and the updater owned by that user.

## Clone and configure

```bash
mkdir -p /home/artemrupasov/projects/d2wm
cd /home/artemrupasov/projects/d2wm

git clone \
  https://github.com/Rupas1k/wardmap-backend.git \
  dota2wardmap-back

git clone \
  https://github.com/Rupas1k/wardmap-stage.git

git -C wardmap-stage lfs pull
```

Create the backend environment:

```bash
cd /home/artemrupasov/projects/d2wm/dota2wardmap-back
./wardmap init
```

Review `.env` before starting production. At minimum, use a strong PostgreSQL
password, add `OPENDOTA_API_KEY` when available, and set the production origin:

```dotenv
CORS_ORIGINS=https://wardmap.rupasov.dev
TRUSTED_PROXY_HOPS=1
```

`.env`, Cloudflare credentials, GitHub tokens, SSH keys, API keys, and database
dumps must never be committed.

## Database restore

For a new database, start infrastructure and restore a custom-format dump:

```bash
cd /home/artemrupasov/projects/d2wm/dota2wardmap-back
./wardmap infra
./wardmap db restore /absolute/path/to/wardmap.dump
```

Restore is destructive to the configured database. It asks for confirmation,
stops application services, runs `pg_restore --clean --if-exists`, and starts
the API and workers afterward. Keep the source dump until the restored service
has been verified.

The maintenance profile in `compose.yaml` is available as a lower-level
alternative when the target database must be dropped and recreated completely.
Set `POSTGRES_RESTORE_PATH` and run:

```bash
docker compose stop api match-collector replay-worker
docker compose --profile maintenance run --rm db-restore
docker compose up --detach --build --wait
```

## Install the production updater

The tracked updater coordinates both repositories. Install a stable symlink:

```bash
ln -sfn \
  /home/artemrupasov/projects/d2wm/dota2wardmap-back/ops/update-wardmap \
  /home/artemrupasov/update-wardmap
```

Run it as `artemrupasov`, or as root and let it switch users automatically:

```bash
/home/artemrupasov/update-wardmap
/home/artemrupasov/update-wardmap backend
/home/artemrupasov/update-wardmap frontend
```

The updater prevents concurrent deployments, performs fast-forward-only Git
pulls, fetches frontend LFS objects, rebuilds changed images, waits for Compose,
and verifies both public endpoints. PostgreSQL and Redis volumes are retained.

From an authenticated development machine, the equivalent command is:

```bash
cd ~/projects/d2wm/dota2wardmap-back
./wardmap deploy
```

## Cloudflare Tunnel

Use one named tunnel with this ingress configuration:

```yaml
tunnel: wardmap-api
credentials-file: /home/artemrupasov/.cloudflared/wardmap-api.json
protocol: http2

ingress:
  - hostname: api.rupasov.dev
    service: http://127.0.0.1:5000
  - hostname: wardmap.rupasov.dev
    service: http://127.0.0.1:4173
  - service: http_status:404
```

HTTP/2 is intentional because outbound QUIC was unreliable on the current
network. Run the tunnel as a persistent user or system service with automatic
restart; do not rely on an interactive terminal process.

The public application does not depend on Tailscale. Tailscale is retained for
SSH, deployment, and private database/cache tunnels.

## Backups

Create a portable PostgreSQL backup with:

```bash
cd /home/artemrupasov/projects/d2wm/dota2wardmap-back
./wardmap db dump backups/wardmap.dump
```

Automate dated backups with a systemd timer or equivalent scheduler. Keep
multiple generations and copy them off the server; a backup stored only beside
the production database does not protect against host or disk failure.

## Verification and troubleshooting

```bash
curl --fail https://api.rupasov.dev/health/ready
curl --fail --head https://wardmap.rupasov.dev

docker compose \
  --project-directory /home/artemrupasov/projects/d2wm/dota2wardmap-back \
  ps --all

docker compose \
  --project-directory /home/artemrupasov/projects/d2wm/wardmap-stage \
  ps --all
```

If a pull refuses to proceed, do not reset the checkout blindly. Inspect
`git status`; production-specific configuration belongs in ignored `.env`
files, not as modifications to tracked Compose or source files.
