import datetime as dt
import json
import os

import common
import eventdb
import requests

from multiprocessing import Process


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
        "earned_platinum": ["earnedTrophies", "platinum"],
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
        "trophy_earned_rate": ["trophyEarnedRate"],
        # Added
        "userid": ["userid"]
    }

    return columns


class psnDict(dict):
    def __init__(self, from_dict, cols, update_cols):
        # Build this dict from an existing dict, one key at a time
        for key in from_dict:
            self[key] = from_dict[key]

        self.db_columns = cols
        self.update_columns = update_cols

    # Enhanced "formatted get" function - for db entry
    def fget(self, key):
        date_type = ["last_updated", "earned_date_time"]
        bool_type = ["trophy_groups", "trophy_hidden", "hidden", "earned"]
        int_type = ["bronze", "silver", "gold", "platinum", "progress",
                    "earned_bronze", "earned_silver", "earned_gold",
                    "earned_platinum", "userid", "trophy_id", "trophy_rare"]

        internal_key = api_to_db().get(key)

        if len(internal_key) == 1:
            value = self.get(internal_key[0])

        elif len(internal_key) == 2:
            if self.get(internal_key[0]):
                value = self[internal_key[0]].get(internal_key[1])

        if key in date_type:

            if value:
                value = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
                value = value.strftime("%Y-%m-%d %H:%M:%S")
                value = f"'{value}'"
            else:
                value = "NULL"

            return value

        if key in bool_type:
            return str(1) if self.get(key) else str(0)

        if key in int_type:
            return str(value)

        else:
            if value:
                value = value.replace("'", "''")
                value = f"'{value}'"

            else:
                value = "NULL"

            return value


def psn_login(npsso):
    params = "&".join([
              "access_type=offline",
              "client_id=09515159-7237-4370-9b40-3806e67c0891",
              "response_type=code",
              "scope=psn:mobile.v2.core psn:clientapp",
              "redirect_uri=com.scee.psxandroid.scecompcall://redirect"
    ])

    code_url = f"https://ca.account.sony.com/api/authz/v3/oauth/authorize?{params}"
    cookies = {"npsso": npsso}

    response = requests.get(code_url, cookies=cookies, allow_redirects=False)

    start = response.headers["Location"].find("?code=")
    end = response.headers["Location"][start:].find("&")

    code = response.headers["Location"][(start + 6):(start + end)]

    login_cookies = response.cookies

    oauth_url = f"https://ca.account.sony.com/api/authz/v3/oauth/token"

    body = {
        "code": code,
        "redirect_uri": "com.scee.psxandroid.scecompcall://redirect",
        "grant_type": "authorization_code",
        "token_format": "jwt"
    }

    headers = {
        "Authorization": "Basic MDk1MTUxNTktNzIzNy00MzcwLTliNDAtMzgwNmU2N2MwODkxOnVjUGprYTV0bnRCMktxc1A="
    }

    response = requests.post(oauth_url, data=body, headers=headers,
                             cookies=login_cookies)

    access_token = json.loads(response.content)["access_token"]

    return access_token


def get_player_summary(access_token, userid):

    # URL is hardcoded to get the trophies summary of logged in user
    summary_url = "https://m.np.playstation.com/api/trophy/v1/users/me/trophyTitles"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    page_size = 800
    offset = 0
    # total is arbitrary, get real value on first call
    total = page_size + 1

    game_summaries = list()

    while offset < total:
        # Parameters are used to set offset and limit, this is because
        # there is a hard limit of 800 items for the request so there
        # could be multiple pages.
        parameters = {
            "limit": page_size,
            "offset": offset
        }

        response = requests.get(summary_url, headers=headers, params=parameters)

        summary_cols = [
            "userid",
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
            "earned_platinum",
            "hidden",
            "last_updated",
        ]

        summary_update = [
            "bronze",
            "silver",
            "gold",
            "platinum",
            "progress",
            "earned_bronze",
            "earned_silver",
            "earned_gold",
            "earned_platinum",
            "hidden",
            "last_updated"
        ]

        summary = json.loads(response.content)

        for game in summary["trophyTitles"]:
            psn_dict = psnDict(game, summary_cols, summary_update)
            psn_dict["userid"] = userid
            game_summaries.append(psn_dict)

        offset = summary.get("nextOffset") or total
        total = summary["totalItemCount"]

    return game_summaries


def get_game_trophies(game_id, np_service_name, access_token, group_id="all"):

    game_url = f"https://m.np.playstation.com/api/trophy/v1/npCommunicationIds/{game_id}/trophyGroups/{group_id}/trophies"

    parameters = {
        "npServiceName": np_service_name
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
        "trophy_group_id"
    ]

    trophies_update = [
        "trophy_hidden",
        "trophy_type",
        "trophy_name",
        "trophy_detail",
        "trophy_icon_url",
        "trophy_group_id"
    ]

    # Modify response to flatten data
    for i in range(0, len(response_dict["trophies"])):
        response_dict["trophies"][i]["trophySetVersion"] = response_dict["trophySetVersion"]
        response_dict["trophies"][i]["npCommunicationId"] = game_id

        response_dict["trophies"][i] = psnDict(response_dict["trophies"][i],
                                               trophies_cols, trophies_update)

    return response_dict["trophies"]


def get_earned_trophies(game_id, np_service_name, access_token, userid,
                        group_id="all", user_id="me") -> dict:

    earned_url = f"https://m.np.playstation.com/api/trophy/v1/users/{user_id}/npCommunicationIds/{game_id}/trophyGroups/{group_id}/trophies"

    parameters = {
        "npServiceName": np_service_name
        }
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(earned_url, headers=headers, params=parameters)

    response_dict = json.loads(response.content)

    earned_cols = [
        "userid",
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

    update_cols = [
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
                                               earned_cols, update_cols)
        response_dict["trophies"][i]["userid"] = userid

    return response_dict["trophies"]


def write_out(file_name, data):
    with open(f"output/{file_name}.json", "w") as target:
        data = json.dumps(data)
        target.write(data)


# TODO: Write logic for complete_fetch, right now it does nothing
def fetch_trophy_data_for_user(user_prefs, npsso, complete_fetch=False) -> dict:

    access_key = psn_login(npsso)
    userid = user_prefs.user_id

    trophy_summary = get_player_summary(access_key, userid)

    # INSERT summary data
    eventdb.insert_into_table_with_columns(trophy_summary,
                                           "psn_summary")

    changed_games_rows = eventdb.get_trophies_that_updated(userid)

    for game in changed_games_rows:
        game_id = game["game_id"]
        game_service_name = game["np_service_name"]
        game_trophies = get_game_trophies(game_id, game_service_name, access_key)

        # Insert trophy data for one game (not specific to player)
        eventdb.insert_into_table_with_columns(game_trophies,
                                               "psn_game_trophies")

        earned_trophies = get_earned_trophies(game_id, game_service_name,
                                              access_key, userid)

        # Insert trophy data for one game for player
        eventdb.insert_into_table_with_columns(earned_trophies,
                                               "psn_earned_trophies")

        # Current datetime, marking the summary for (approx) time updated
        update_now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        eventdb.update_trophies_last_checked(
            userid, game["np_service_name"], game["trophy_set_version"],
            game["game_id"], update_now
        )

    return trophy_summary


def api_fetch_background(user_prefs, sso_key, complete_fetch=False):

    # fetch_trophy_data_for_user(user_prefs, sso_key, complete_fetch)

    file_proc_bkg = Process(target=fetch_trophy_data_for_user,
                            args=(user_prefs, sso_key, complete_fetch),
                            daemon=True)
    file_proc_bkg.start()

    status_message = "API update started."

    return status_message
