import json
import datetime as dt
import pytz as tz
import common, eventdb
from pathlib import Path


class foursquareImporter:
    def __init__(self, directory):
        target_dir = Path(directory)
        self.checkins = dict()

        for target_file in target_dir.iterdir():
            with open(target_file, "r", encoding="utf-8") as file:
                file = file.read()
                json_file = json.loads(file)

            for event in json_file["items"]:
                # add event to list as an "enhanced" dict
                add_event = foursquareImporterEvent(**event)
                self.checkins[add_event["id"]] = add_event

    def add_to_database(self, user_prefs):
        eventdb.insert_foursquare_checkins(self.checkins, user_prefs)

# A tiny "enhanced" dict class that extends dict and adds a useful utility for converting timestamps
class foursquareImporterEvent(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_datetime(self):
        return dt.datetime.fromtimestamp(self["createdAt"], tz.timezone("UTC"))

    def get_date(self):
        return self.get_datetime().date()

    def get_time(self):
        return self.get_datetime().time()

    def get_time_str(self):
        return self.get_time().strftime("%H:%M:%S")

    def get_date_str(self):
        return self.get_date().strftime("%Y-%m-%d")

    def get_venue_name_for_sql(self):
        return self["venue"]["name"].replace("'","''")


def process_from_file(file_path):
    current_user = common.UserPreferences(1)
    process_dir = common.unpack_and_store_files(file_path, "output")
    checkin_import = foursquareImporter(process_dir)
    checkin_import.add_to_database(current_user)
    common.cleanup(process_dir)
