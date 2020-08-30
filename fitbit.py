import json
import datetime
import eventdb
from pathlib import Path


class FitbitImporter:
    def __init__(self, directory):
        self.__process_directory(directory)

    def __len__(self):
        return len(self.json_list)

    def __process_directory(self, dir_path):
        target_dir = Path(dir_path)
        self.json_list = list()

        for target_file in target_dir.iterdir():
            with open(target_file, "r") as file:
                file = file.read()
                json_file = json.loads(file)
            self.json_list += json_file

    def get_item(self, item_position):

        return self.json_list[item_position]


class FitbitSleepImporter(FitbitImporter):
    def __init__(self, directory):
        super().__init__(directory)
        self.data_type = "sleep"

    def add_to_database(self):
        return f"Let's add some {self.data_type} data to the db!"


if __name__ == "__main__":
    all_data = FitbitSleepImporter("data/Fitbit Sleep")
    print(all_data.get_item(492))
    print(all_data.add_to_database())
    print(len(all_data))
