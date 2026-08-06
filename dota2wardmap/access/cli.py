from datetime import UTC, datetime

import click
from flask import Flask
from sqlalchemy import select

from ..domain import AccessLevel
from ..extensions import db
from ..models import ApiKey
from .keys import generate_api_key


def register_key_commands(app: Flask) -> None:
    keys = click.Group("keys", help="Create, list, and revoke API keys.")

    @keys.command("create")
    @click.option("--owner", required=True, help="User or service that owns the key.")
    @click.option(
        "--access",
        "access_level",
        type=click.Choice([AccessLevel.ADVANCED.value, AccessLevel.ADMIN.value]),
        default=AccessLevel.ADVANCED.value,
    )
    def create_key(owner: str, access_level: str) -> None:
        raw_key, prefix, digest = generate_api_key()
        api_key = ApiKey()
        api_key.owner = owner
        api_key.key_prefix = prefix
        api_key.key_hash = digest
        api_key.access_level = access_level
        db.session.add(api_key)
        db.session.commit()
        click.echo(f"API key (shown once): {raw_key}")
        click.echo(f"Owner: {owner}; access: {access_level}; prefix: {prefix}")

    @keys.command("list")
    def list_keys() -> None:
        rows = db.session.execute(select(ApiKey).order_by(ApiKey.id)).scalars()
        for api_key in rows:
            state = "revoked" if api_key.revoked_at else "active"
            click.echo(f"{api_key.id}\t{api_key.key_prefix}\t{api_key.access_level}\t{state}\t{api_key.owner}")

    @keys.command("revoke")
    @click.argument("prefix")
    def revoke_key(prefix: str) -> None:
        api_key = db.session.execute(select(ApiKey).where(ApiKey.key_prefix == prefix)).scalar_one_or_none()
        if api_key is None:
            raise click.ClickException(f"No API key has prefix {prefix}")
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(UTC)
            db.session.commit()
        click.echo(f"Revoked {prefix}")

    app.cli.add_command(keys)
