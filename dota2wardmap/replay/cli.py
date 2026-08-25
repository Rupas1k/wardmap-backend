import click
from flask import Flask

from ..integrations import opendota
from ..team_metadata import refresh_stale_team_metadata
from .backfill import backfill_match_player_sides, backfill_match_teams
from .collector import sync_league
from .reparse import plan_league_reparse, queue_league_reparse


def register_replay_commands(app: Flask) -> None:
    @app.cli.command("refresh-league")
    @click.argument("league_id", type=click.IntRange(min=1))
    def refresh_league_command(league_id: int) -> None:
        """Discover matches and retry unparsed replay jobs for a league."""
        try:
            queued, total = sync_league(league_id, refresh_unparsed_jobs=True)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        except opendota.OpenDotaError as error:
            raise click.ClickException("OpenDota is temporarily unavailable") from error

        click.echo(f"League {league_id}: refreshed {queued} unparsed jobs from {total} matches.")

    @app.cli.command("reparse-leagues")
    @click.option(
        "--league-id",
        "league_ids",
        type=click.IntRange(min=1),
        multiple=True,
        required=True,
        help="League to reparse. May be repeated.",
    )
    @click.option("--yes", is_flag=True, help="Skip the destructive-action confirmation.")
    def reparse_leagues_command(league_ids: tuple[int, ...], yes: bool) -> None:
        """Remove parsed league matches and queue them again."""
        try:
            plan = plan_league_reparse(league_ids)
        except ValueError as error:
            raise click.ClickException(str(error)) from error

        leagues = ", ".join(map(str, plan.league_ids))
        click.echo(
            f"Leagues {leagues}: {len(plan.match_ids)} matches and "
            f"{plan.ward_count} wards will be removed and reparsed."
        )
        if not plan.match_ids:
            click.echo("Nothing to reparse.")
            return
        if not yes and not click.confirm("Continue?"):
            raise click.Abort()

        try:
            queued = queue_league_reparse(plan)
        except ValueError as error:
            raise click.ClickException(str(error)) from error

        click.echo(f"Queued {queued} matches for reparsing.")

    @app.cli.command("backfill-match-teams")
    @click.option("--limit", type=click.IntRange(min=1), help="Maximum matches to process.")
    def backfill_match_teams_command(limit: int | None) -> None:
        """Fetch team and result metadata for existing parsed matches."""
        updated, failed = backfill_match_teams(limit)
        click.echo(f"Updated {updated} matches; {failed} failed.")

    @app.cli.command("backfill-player-sides")
    @click.option(
        "--league-id",
        "league_ids",
        type=click.IntRange(min=1),
        multiple=True,
        help="Restrict the refill to a league. May be repeated.",
    )
    @click.option("--limit", type=click.IntRange(min=1), help="Maximum matches to process.")
    @click.option(
        "--delay",
        "delay_seconds",
        type=click.FloatRange(min=0),
        default=1.5,
        show_default=True,
        help="Seconds to wait between OpenDota requests.",
    )
    def backfill_player_sides_command(
        league_ids: tuple[int, ...],
        limit: int | None,
        delay_seconds: float,
    ) -> None:
        """Fetch participant sides for existing parsed matches."""
        matches, players, failed = backfill_match_player_sides(league_ids, limit, delay_seconds)
        click.echo(f"Updated {players} players in {matches} matches; {failed} matches failed.")

    @app.cli.command("refresh-teams")
    @click.option("--max-age-days", type=click.IntRange(min=0), default=30, show_default=True)
    @click.option("--limit", type=click.IntRange(min=1), help="Maximum teams to process.")
    def refresh_teams_command(max_age_days: int, limit: int | None) -> None:
        """Refresh names, tags, and logos for stale teams."""
        updated, failed = refresh_stale_team_metadata(max_age_days, limit)
        click.echo(f"Updated {updated} teams; {failed} failed.")
