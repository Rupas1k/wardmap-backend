from .access import bp as access_blueprint
from .matches import bp as matches_blueprint
from .players import bp as players_blueprint
from .teams import bp as teams_blueprint
from .wards import bp as wards_blueprint

blueprints = (access_blueprint, matches_blueprint, players_blueprint, teams_blueprint, wards_blueprint)

__all__ = ["blueprints"]
