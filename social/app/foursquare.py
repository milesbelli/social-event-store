import json
import datetime as dt
import pytz as tz
import common, eventdb
from pathlib import Path


class foursquareImporter:
    def __init__(self, directory):
        target_dir = Path(directory)
        self.checkin_list = list()

        for target_file in target_dir.iterdir():
            with open(target_file, "r", encoding="utf-8") as file:
                file = file.read()
                json_file = json.loads(file)

            for event in json_file["items"]:
                # add event to list as an "enhanced" dict
                self.checkin_list.append(foursquareImporterEvent(**event))

    def add_to_database(self):
        pass

# A tiny "enhanced" dict class that extends dict and adds a useful utility for converting timestamps
class foursquareImporterEvent(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_datetime(self):
        return dt.datetime.fromtimestamp(self["createdAt"], tz.timezone("UTC"))


def process_from_file(file_path):
    current_user = common.UserPreferences(1)
    process_dir = common.unpack_and_store_files(file_path, "output")
    checkin_import = foursquareImporter(process_dir)
    checkin_import.add_to_database(current_user)
    common.cleanup(process_dir)
