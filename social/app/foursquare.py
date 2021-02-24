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

    def get_shout_for_sql(self):
        shout_text = self.get('shout')
        if shout_text:
            shout_text = shout_text.replace("'","''")
            return f"'{shout_text}'"
        else:
            return "NULL"

    def get_event_id_for_sql(self):
        event = self.get("event")
        event_id = event.get("id") if event else None
        out_str = f"'{event_id}'" if event_id else "NULL"
        return out_str

    def get_event_name_for_sql(self):
        event = self.get("event")
        event_name = event.get("name").replace("'", "''") if event else None
        out_str = f"'{event_name}'" if event_name else "NULL"
        return out_str

    def get_primary_category_id_and_name(self):
        event = self.get("event")
        event_categories = event.get("categories") if event else []
        cat_id = None
        cat_name = None
        for cat in event_categories:
            if cat["primary"]:
                cat_id = cat["id"]
                cat_name = cat["name"].replace("'", "''")
                break
        cat_id = f"'{cat_id}'" if cat_id else "NULL"
        cat_name = f"'{cat_name}'" if cat_name else "NULL"

        return {"id": cat_id, "name": cat_name}


def process_from_file(file_path):
    current_user = common.UserPreferences(1)
    process_dir = common.unpack_and_store_files(file_path, "output")
    checkin_import = foursquareImporter(process_dir)
    checkin_import.add_to_database(current_user)
    common.cleanup(process_dir)
