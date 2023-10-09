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


def fetch_live_games(step, mmr_threshold=8000):
    query = 'GetLiveGames'
    matches = execute_graphql(query, {'take': step, 'skip': 0})['live']['matches']
    i = 0
    while matches[-1]['averageRank'] > mmr_threshold:
        matches += execute_graphql(query, {'take': step, 'skip': step * i})['live']['matches']
        i += 1
    return [match for match in matches if match['averageRank'] > mmr_threshold]


def execute_graphql(query_name, params):
    with open(ROOT_DIR / Path(f'graphql/{query_name}.graphql'), encoding='utf8') as query:
        return client.execute(gql(query.read()), variable_values=params)


if __name__ == '__main__':
    print(len(fetch_live_games(150)))
