import os
import dotenv
from pathlib import Path

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

from definitions import ROOT_DIR


dotenv.load_dotenv()

API_URL = 'https://api.stratz.com/graphql'
API_TOKEN = os.environ['API_TOKEN']

transport = AIOHTTPTransport(url=API_URL, headers={'Authorization': API_TOKEN})
client = Client(transport=transport, fetch_schema_from_transport=True, execute_timeout=30)


def fetch_live_games(step=100, mmr_threshold=8000):
    matches = execute_graphql('GetPublicMatches', {'take': step, 'skip': 0})['live']['matches']
    i = 0
    to_add = 1
    while matches[-1]['averageRank'] > mmr_threshold and to_add:
        to_add = execute_graphql('GetPublicMatches', {'take': step, 'skip': step * i})['live']['matches']
        matches += to_add
        i += 1
    matches = [match for match in matches if match['averageRank'] > mmr_threshold]
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

def execute_graphql(query_name, params):
    with open(ROOT_DIR / Path(f'graphql/{query_name}.graphql'), encoding='utf8') as query:
        return client.execute(gql(query.read()), variable_values=params)


if __name__ == '__main__':
    print(len(fetch_live_games(150)))
