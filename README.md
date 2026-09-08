# Wardmap backend

API and replay-processing pipeline for [Wardmap](https://wardmap.rupasov.dev).

## Development

Requires Docker with Compose, Python 3.13, Rust, curl, and SSH.

```bash
./wardmap init
./wardmap doctor
./wardmap up
./wardmap health
```

The API is available at <http://localhost:5000>. Run `./wardmap help` for the
complete command list.

## Checks

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt ruff pyright

ruff check .
ruff format --check .
pyright
python -m pytest
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
