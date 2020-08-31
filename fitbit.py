import json
import datetime
import eventdb
import common
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

    def list_all_ids(self):
        output_ids = list()

        for entry in self.json_list:
            output_ids.append(entry["logId"])

        return output_ids


class FitbitSleepImporter(FitbitImporter):
    def __init__(self, directory):
        super().__init__(directory)
        self.__enforce_unique_set()

    def add_to_database(self, user_prefs):
        eventdb.insert_fitbit_sleep(self.json_list, user_prefs)
        return f"Up to {len(self)} entries can be added to the db!"

    # Fitbit sleep data can contain duplicates! They must be removed at some point, so might as well do it here.
    def __enforce_unique_set(self):
        logid_index = set()
        unique_list = list()

        for json_item in self.json_list:
            if json_item["logId"] not in logid_index:
                unique_list.append(json_item)
                logid_index.add(json_item["logId"])

        self.json_list = unique_list


if __name__ == "__main__":
    all_data = FitbitSleepImporter("data/Fitbit Sleep")
    print(all_data.get_item(106))
    my_user = common.UserPreferences(1)


    maxlog = 0
    for item in all_data.json_list:
        maxlog = item["logId"] if item["logId"] > maxlog else maxlog


    all_data.add_to_database(my_user)
    print(len(all_data))

    print(maxlog)
