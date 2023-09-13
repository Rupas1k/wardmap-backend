import os
import dotenv
from pathlib import Path
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

from definitions import ROOT_DIR

dotenv.load_dotenv()

API_URL = 'https://api.stratz.com/graphql'
API_TOKEN = os.environ['API_TOKEN']

transport = AIOHTTPTransport(url=API_URL,  headers={'Authorization': API_TOKEN})
client = Client(transport=transport, fetch_schema_from_transport=True, execute_timeout=30)


def fetch_live_games(step, mmr_threshold=8000):
    query = 'GetLiveGames'
    matches = execute_graphql(query, {'take': step, 'skip': 0})['live']['matches']
    i = 0
    while matches[-1]['averageRank'] > mmr_threshold:
        matches += execute_graphql(query, {'take': step, 'skip': step * i})['live']['matches']
        i += 1
    return [match for match in matches if match['averageRank'] > mmr_threshold]


def fetch_league_games_data(league_id, step, skip=0):
    query = 'GetLeagueMatches'
    result = execute_graphql(query, {'leagueId': league_id, 'take': step, 'skip': skip})
    matches = []
    for match_data in result['league']['matches']:
        try:
            match = parse_match(match_data)
            matches.append(match)
        except Exception as e:
            import traceback
            print(match_data['id'])
            print(traceback.format_exc())
            continue
    return matches


def parse_match(match_data):
    if len(match_data) and match_data:
        players = {}
        for player in match_data['players']:
            players[player['playerSlot']] = (player['steamAccountId'], player['isRadiant'])

        ward_events = match_data['playbackData']['wardEvents'] if 'playbackData' in match_data and match_data['playbackData'] else []
        wards_temp = dict()

        for event in ward_events:
            if event['action'] == 'SPAWN':
                lead_1 = match_data['radiant_networth_lead'][event['time'] // 60 + 1 if event['time'] > -60 else 0]
                lead_2 = match_data['radiant_networth_lead'][event['time'] // 60 + 2 if event['time'] // 60 + 2 < len(match_data['radiant_networth_lead']) else -1]
                ward = {
                    'is_obs': event['wardType'] == 'OBSERVER',
                    'x': event['positionX'],
                    'y': event['positionY'],
                    'is_radiant': players[event['fromPlayer']][1],
                    'time_placed': event['time'],
                    'player_placed': event['fromPlayer'],
                    'duration': -event['time'],
                    'player_destroyed': None,
                    'radiant_networth_lead': lead_1 + int((lead_2 - lead_1) / 60 * (event['time'] - event['time'] // 60 * 60))
                }
                wards_temp[event['indexId']] = ward
            else:
                wards_temp[event['indexId']]['duration'] += event['time']
                wards_temp[event['indexId']]['player_destroyed'] = event['playerDestroyed']

        wards = wards_temp.values()

        match = {
            'id': match_data['id'],
            'league_id': match_data['leagueId'],
            'tournament_id': match_data['tournamentId'],
            'players': [val[0] for val in players.values()],
            'wards': [{
                'match_id': match_data['id'],
                'player_placed_id': players[ward['player_placed']][0],
                'player_destroyed_id': players[ward['player_destroyed']][0] if ward['player_destroyed'] else None,
                'is_obs': ward['is_obs'],
                'is_radiant': ward['is_radiant'],
                'time_placed': ward['time_placed'],
                'duration': ward['duration'] if ward['duration'] > 0 else ward['duration'] + match_data[
                    'durationSeconds'],
                'x_pos': ward['x'],
                'y_pos': ward['y'],
                'radiant_networth_lead': ward['radiant_networth_lead']
            } for ward in wards]
        }
        return match
    return []


def execute_graphql(query_name, params):
    with open(ROOT_DIR / Path(f'graphql/{query_name}.graphql'), encoding='utf8') as query:
        return client.execute(gql(query.read()), variable_values=params)


if __name__ == '__main__':
    print(len(fetch_live_games(150)))
