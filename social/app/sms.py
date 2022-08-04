import json
import datetime as dt
import pytz as tz
import common, eventdb
from pathlib import Path
import requests as r


class SmsImporter:
    def __init__(self, directory):
        target_dir = Path(directory)
        self.texts = dict()

        for target_file in target_dir.iterdir():
            with open(target_file, "r", encoding="utf-8") as file:
                file = file.read()
                json_file = json.loads(file)

            for event in json_file:
                # add event to list as an "enhanced" dict
                sms_event = SmsMessage(**event)
                self.texts[event["id"]] = sms_event

    def add_to_database(self, user_prefs):
        eventdb.insert_sms_into_db(self.texts, user_prefs)


class SmsMessage(dict):
    def sql_body(self):
        if self.get("body"):
            sql_body = self.get("body").replace("'", "''").replace("\\", "\\\\")
            return f"'{sql_body}'"
        else:
            return "NULL"

    def get_sql(self, key):
        value = self.get(key)
        if value == "":
            value = None
        return f"'{value}'" if value else "NULL"


def process_from_file(directory):
    current_user = common.UserPreferences(1)
    process_dir = common.unpack_and_store_files(directory, None, "sms")
    sms_import = SmsImporter(process_dir)
    sms_import.add_to_database(current_user)
    common.cleanup(process_dir)


if __name__ == "__main__":
    process_from_file("preprocessors/sms/output")
