from .. import create_worker_app
from .service import run_replay_worker


def main() -> None:
    app = create_worker_app()
    with app.app_context():
        run_replay_worker()


if __name__ == "__main__":
    main()
