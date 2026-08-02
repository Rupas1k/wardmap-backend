import os
import dotenv
from pathlib import Path

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

from extensions import ROOT_DIR


dotenv.load_dotenv()

API_URL = 'https://api.stratz.com/graphql'
API_TOKEN = os.environ['API_TOKEN']

transport = AIOHTTPTransport(url=API_URL, headers={'Authorization': API_TOKEN, "User-Agent": "STRATZ_API"})
client = Client(transport=transport, fetch_schema_from_transport=True, execute_timeout=30)


def fetch_live_games(step=100, mmr_threshold=8000):
    matches = execute_graphql('GetPublicMatches', {'take': step, 'skip': 0})['live']['matches']
    i = 0
    while matches and matches[-1]['averageRank'] is not None and matches[-1]['averageRank'] > mmr_threshold:
        to_add = execute_graphql('GetPublicMatches', {'take': step, 'skip': step * i})['live']['matches']
        matches += to_add
        i += 1
    matches = [match for match in matches if match['averageRank'] is not None and match['averageRank'] > mmr_threshold]
    league_matches = execute_graphql('GetLeagueMatches', {'take': step, 'skip': 0})['live']['matches']
    matches += league_matches
    return matches


def fetch_league_games(league_id, step=100):
    matches = execute_graphql('GetAllLeagueMatches', {'league_id': league_id, 'take': step, 'skip': 0})['league']['matches']
    i = 0
    while len(matches) == step * (i + 1):
        matches += execute_graphql('GetAllLeagueMatches', {'league_id': league_id, 'take': step, 'skip': step * i})['league']['matches']
        i += 1
    return matches


def fetch_league_players(league_id):
    players = execute_graphql('GetLeaguePlayers', {'league': league_id})['league']['tables']['tablePlayers']
    players_return = []
    for player in players:
        account = player['steamAccount']
        name = account['proSteamAccount']['name'] if account.get('proSteamAccount') and account['proSteamAccount'].get('name') else None
        players_return.append({
            'id': account['id'],
            'name': name,
        })
    return players_return


def fetch_league_info(league_id):
    league_info = execute_graphql('GetLeagueInfo', {'league': league_id})['league']
    return league_info


def execute_graphql(query_name, params):
    with open(ROOT_DIR / Path(f'graphql/{query_name}.graphql'), encoding='utf8') as query:
        return client.execute(gql(query.read()), variable_values=params)


if __name__ == '__main__':
    import json
    print(json.dumps(fetch_league_info(15728), indent=4))
