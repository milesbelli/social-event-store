import json
import datetime
import eventdb
from pathlib import Path


class FitbitImporter:
    def __init__(self, directory):
        self.json_list = self.process_directory(directory)

    def process_directory(self, dir_path):
        target_dir = Path(dir_path)
        list_of_events = list()

        for target_file in target_dir.iterdir():
            list_of_events += self.json_load_file(target_file)

        return list_of_events

    def json_load_file(self, filepath):
        with open(filepath, "r") as file:
            file = file.read()
            json_file = json.loads(file)

        return json_file

    def get_item(self, item_position):

        return self.json_list[item_position]


class FitbitSleepImporter(FitbitImporter):
    def add_to_database(self):

        return "Let's add this stuff to the db!"


if __name__ == "__main__":
    all_data = FitbitSleepImporter("data/Fitbit Sleep")
    print(all_data.get_item(492))
    print(all_data.add_to_database())
