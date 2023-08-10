import dotenv



class Parser:
    def __init__(self):
        pass




if __name__ == '__main__':
    dotenv.load_dotenv()

    api = StratzApi()
    app = Parser()

    # matches = api.fetch_league_games_data(15475, 10)
    # app.insert_league_matches(15475, 10, 0)
