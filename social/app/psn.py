import requests
import json
import datetime
import os


def api_to_db():

    columns = {
        # Summary
        "np_service_name": ["npServiceName"],
        "game_id": ["npCommunicationId"],
        "trophy_set_version": ["trophySetVersion"],
        "game_title": ["trophyTitleName"],
        "title_detail": ["trophyTitleDetail"],
        "icon_url": ["trophyTitleIconUrl"],
        "platform": ["trophyTitlePlatform"],
        "trophy_groups": ["hasTrophyGroups"],
        "bronze": ["definedTrophies", "bronze"],
        "silver": ["definedTrophies", "silver"],
        "gold": ["definedTrophies", "gold"],
        "platinum": ["definedTrophies", "platinum"],
        "progress": ["progress"],
        "earned_bronze": ["earnedTrophies", "bronze"],
        "earned_silver": ["earnedTrophies", "silver"],
        "earned_gold": ["earnedTrophies", "gold"],
        "earned_platium": ["earnedTrophies", "platinum"],
        "hidden": ["hiddenFlag"],
        "last_updated": ["lastUpdatedDateTime"],
        # Game Trophies
        "trophy_id": ["trophyId"],
        "trophy_hidden": ["trophyHidden"],
        "trophy_type": ["trophyType"],
        "trophy_name": ["trophyName"],
        "trophy_detail": ["trophyDetail"],
        "trophy_icon_url": ["trophyIconUrl"],
        "trophy_group_id": ["trophyGroupId"],
        # Earned Trophies
        "earned": ["earned"],
        "earned_date_time": ["earnedDateTime"],
        "trophy_rare": ["trophyRare"],
        "trophy_earned_rate": ["trophyEarnedRate"]
    }

    return columns


class psnDict(dict):
    def __init__(self, from_dict, cols):
        # Build this dict from an existing dict, one key at a time
        for key in from_dict:
            self[key] = from_dict[key]

        self.db_columns = cols

    # Enhanced "formatted get" function - for db entry
    def fget(self, key):
        date_type = ["last_updated", "earned_date_time"]
        bool_type = ["trophy_groups", "trophy_hidden", "earned"]

        internal_key = api_to_db().get(key)

        if len(internal_key) == 1:
            value = self.get(internal_key[0])

        elif len(internal_key) == 2:
            if self.get(internal_key[0]):
                value = self[internal_key[0]].get(internal_key[1])

        if key in date_type:
            value = self.get(key) or "NULL"

            # Further conversion needed

            return value

        if key in bool_type:
            return 1 if self[key] else 0

        else:
            if value:
                value = value.replace("'", "''")
                value = f"'{value}'"

            return value


def psn_login(npsso):
    code_url = "https://ca.account.sony.com/api/authz/v3/oauth/authorize?access_type=offline&client_id=ac8d161a-d966-4728-b0ea-ffec22f69edc&redirect_uri=com.playstation.PlayStationApp%3A%2F%2Fredirect&response_type=code&scope=psn%3Amobile.v1%20psn%3Aclientapp"
    cookies = {"npsso": npsso}

    response = requests.get(code_url, cookies=cookies, allow_redirects=False)

    start = response.headers["Location"].find("?code=")
    end = response.headers["Location"][start:].find("&")

    code = response.headers["Location"][(start + 6):(start + end)]

    login_cookies = response.cookies

    oauth_url = f"https://ca.account.sony.com/api/authz/v3/oauth/token"

    body = {
        "code": code,
        "redirect_uri": "com.playstation.PlayStationApp://redirect",
        "grant_type": "authorization_code",
        "token_format": "jwt"
    }

    headers = {
        "Authorization": "Basic YWM4ZDE2MWEtZDk2Ni00NzI4LWIwZWEtZmZlYzIyZjY5ZWRjOkRFaXhFcVhYQ2RYZHdqMHY="
    }

    response = requests.post(oauth_url, data=body, headers=headers,
                             cookies=login_cookies)

    access_token = json.loads(response.content)["access_token"]

    return access_token


def get_player_summary(access_token):

    summary_url = "https://m.np.playstation.com/api/trophy/v1/users/me/trophyTitles"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(summary_url, headers=headers)

    summary_cols = [
        "np_service_name",
        "game_id",
        "trophy_set_version",
        "game_title",
        "title_detail",
        "icon_url",
        "platform",
        "trophy_groups",
        "bronze",
        "silver",
        "gold",
        "platinum",
        "progress",
        "earned_bronze",
        "earned_silver",
        "earned_gold",
        "earned_platium",
        "hidden",
        "last_updated",
    ]

    summary = json.loads(response.content)

    summary = psnDict(summary, summary_cols)

    return summary


def get_game_trophies(game_id, access_token, group_id="all"):

    game_url = f"https://m.np.playstation.com/api/trophy/v1/npCommunicationIds/{game_id}/trophyGroups/{group_id}/trophies"

    parameters = {
        "npServiceName": "trophy"
        }

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(game_url, headers=headers, params=parameters)

    response_dict = json.loads(response.content)

    trophies_cols = [
        "game_id",
        "trophy_set_version",
        "trophy_id",
        "trophy_hidden",
        "trophy_type",
        "trophy_name",
        "trophy_detail",
        "trophy_icon_url",
        "trophy_group_id",
    ]

    # Modify response to flatten data
    for i in range(0, len(response_dict["trophies"])):
        response_dict["trophies"][i]["trophySetVersion"] = response_dict["trophySetVersion"]
        response_dict["trophies"][i]["npCommunicationId"] = game_id

        response_dict["trophies"][i] = psnDict(response_dict["trophies"][i],
                                               trophies_cols)

    return response_dict


def get_earned_trophies(game_id, access_token,
                        group_id="all", user_id="me") -> dict:

    earned_url = f"https://m.np.playstation.com/api/trophy/v1/users/{user_id}/npCommunicationIds/{game_id}/trophyGroups/{group_id}/trophies?npServiceName=trophy"

    parameters = {
        "npServiceName": "trophy"
        }
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(earned_url, headers=headers, params=parameters)

    response_dict = json.loads(response.content)

    earned_cols = [
        "trophy_id",
        "game_id",
        "trophy_set_version",
        "trophy_hidden",
        "trophy_type",
        "earned",
        "earned_date_time",
        "trophy_rare",
        "trophy_earned_rate"
    ]

    # Modify response to flatten data and make SQL friendly
    # for trophy in response_dict["trophies"]:
    for i in range(0, len(response_dict["trophies"])):
        response_dict["trophies"][i]["trophySetVersion"] = response_dict["trophySetVersion"]
        response_dict["trophies"][i]["npCommunicationId"] = game_id

        response_dict["trophies"][i] = psnDict(response_dict["trophies"][i],
                                               earned_cols)

    return response_dict


def write_out(file_name, data):
    with open(f"output/{file_name}.json", "w") as target:
        data = json.dumps(data)
        target.write(data)


def fetch_trophy_data_for_user(npsso, complete_fetch=False) -> dict:

    trophy_data = dict()
    access_key = psn_login(npsso)

    trophy_data["summary"] = get_player_summary(access_key)
    trophy_data["game_trophies"] = []
    trophy_data["earned_trophies"] = []

    unchanged_games = dict()
    if not complete_fetch:
        # build unchanged games dict for compares
        pass

    for game in [trophy_data["summary"]["trophyTitles"][0]]:  # TODO: change this back!
        game_id = game["npCommunicationId"]
        if not unchanged_games.get(game_id):
            trophy_data["game_trophies"].append(get_game_trophies(game_id,
                                                                  access_key)
                                                )

            # write_out(f"{game_id}_trophies",
            #           trophy_data["game_trophies"][-1])

            trophy_data["earned_trophies"].append(
                    get_earned_trophies(game_id, access_key)
                                                  )

            # write_out(f"{game_id}_earned",
            #           trophy_data["earned_trophies"][-1])

    return trophy_data


# Log into PSN in browser and get from https://ca.account.sony.com/api/v1/ssocookie
# For dev purposes, I'm putting this in the environment variables

sso_key = os.getenv("PSN_KEY")

trophies = fetch_trophy_data_for_user(sso_key, complete_fetch=True)

for game in trophies["earned_trophies"]:
    if game["trophies"][0].fget("game_id") != "'NPWR22009_00'":
        print(game)

for game in trophies["game_trophies"]:
    if game["trophies"][0].fget("game_id") == "'NPWR22009_00'":
        print(game)
