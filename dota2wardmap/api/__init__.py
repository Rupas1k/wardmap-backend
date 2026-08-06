from .access import bp as access_blueprint
from .clusters import bp as clusters_blueprint
from .matches import bp as matches_blueprint
from .wards import bp as wards_blueprint

blueprints = (access_blueprint, clusters_blueprint, matches_blueprint, wards_blueprint)

__all__ = ["blueprints"]
