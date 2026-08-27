# Development setup

This guide configures a new machine for both repositories:

```text
~/projects/d2wm/
├── dota2wardmap-back/  # Rupas1k/wardmap-backend
└── wardmap-stage/      # production frontend repository
```

The directory name `dota2wardmap-back` is retained because the production
updater currently expects it. `wardmap-stage` is the main frontend repository;
it is not a separate staging environment.

## Prerequisites

Install these once:

- Git, Git LFS, and GitHub CLI
- Docker with the Compose plugin
- Python 3.13 and virtual-environment support
- Node.js 22 and npm
- Rust through rustup with the `wasm32-unknown-unknown` target
- `wasm-pack` 0.15.0
- Tailscale only if this machine will inspect or deploy production

On Windows, use WSL2 and enable Docker Desktop integration for the selected
Linux distribution. Run all project commands inside WSL rather than mixing
Windows and Linux checkouts.

Authenticate GitHub and configure predictable pulls:

```bash
gh auth login
gh auth setup-git
git lfs install
git config --global pull.rebase true
```

## Clone both repositories

```bash
mkdir -p ~/projects/d2wm
cd ~/projects/d2wm

git clone \
  https://github.com/Rupas1k/wardmap-backend.git \
  dota2wardmap-back

git clone \
  https://github.com/Rupas1k/wardmap-stage.git
```

Both repositories are private, so `gh auth login` must be completed first.

## Backend

The application and infrastructure run in Docker. Create a local `.env` from
the committed example and start the stack:

```bash
cd ~/projects/d2wm/dota2wardmap-back

./wardmap init
./wardmap doctor
./wardmap up
./wardmap health
```

Local endpoints:

| Component | Address |
| --- | --- |
| API | `http://localhost:5000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

The default `.env` is suitable for isolated local development. Add an
`OPENDOTA_API_KEY` when higher OpenDota limits are required. Never copy the
production `.env` to a development machine.

### Python checks

The console runs tests from a local virtual environment so editor tooling and
CI use the same Python code:

```bash
cd ~/projects/d2wm/dota2wardmap-back

python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt ruff pyright

ruff check .
pyright
./wardmap test
```

Installing `requirements.txt` compiles the Rust/PyO3 replay parser. Ensure a
working Rust toolchain and native build tools are available first.

## Frontend

Fetch the Git LFS map assets and install the locked npm dependencies:

```bash
cd ~/projects/d2wm/wardmap-stage

git lfs pull
rustup target add wasm32-unknown-unknown
cargo install wasm-pack --version 0.15.0
npm ci
```

Create the ignored `.env.local` file:

```dotenv
VITE_API_URL=http://localhost:5000
```

Start Vite with hot reload:

```bash
npm run dev
```

Open <http://localhost:5173>. The browser talks to the local backend on port
`5000`; production is not involved.

Run the frontend CI checks locally with:

```bash
npm run build:wasm
npm run typecheck
npm run lint
npm run format:check
cargo test --workspace
npm run build
```

## Daily workflow

Start or refresh the backend from one terminal:

```bash
cd ~/projects/d2wm/dota2wardmap-back
git pull
./wardmap up
./wardmap logs api replay-worker
```

Start the frontend from another terminal:

```bash
cd ~/projects/d2wm/wardmap-stage
git pull
npm ci
npm run dev
```

Use feature branches for changes and push only after the relevant checks pass:

```bash
git switch -c feature/short-description
git add .
git commit -m "Describe the change"
git push -u origin HEAD
```

After production changes are merged and pushed, deploy both repositories from
the backend checkout:

```bash
./wardmap deploy
```

Deployment requires Tailscale access to `home-pc`. See
[Server deployment](deployment.md) for the server-side configuration.

## Production access from a workstation

Tailscale is not required for local development. When production access is
needed:

```bash
tailscale status
tailscale ping 100.68.5.52
ssh artemrupasov@100.68.5.52
```

To inspect production PostgreSQL or Redis without exposing their ports:

```bash
./wardmap tunnel
```

This forwards PostgreSQL to `localhost:15432` and Redis to `localhost:16379`.
