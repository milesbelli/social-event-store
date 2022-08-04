import json
import datetime
import common, eventdb
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
        print(f"[{datetime.datetime.now()}] Parsing files from directory.")
        start_process_time = datetime.datetime.now()
        super().__init__(directory)
        self.__enforce_unique_set()
        print(f"[{datetime.datetime.now()}] Completed sleep data processing of directory. "
              f"Time taken: {datetime.datetime.now() - start_process_time}")

    def add_to_database(self, user_prefs):
        eventdb.insert_fitbit_sleep(self.json_list, user_prefs)

    # Fitbit sleep data can contain duplicates! They must be removed at some point, so might as well do it here.
    def __enforce_unique_set(self):
        logid_index = set()
        unique_list = list()

        for json_item in self.json_list:
            if json_item["logId"] not in logid_index:
                unique_list.append(json_item)
                logid_index.add(json_item["logId"])

        self.json_list = unique_list


class FitbitSleepEvent:
    def __init__(self, sleep_id):
        # Query will retrieve one entry, so just grab first result and store it in this object
        data = eventdb.get_fitbit_sleep_event(sleep_id)[0]
        if data:
            self.datetime = datetime.datetime.combine(data["eventdate"], datetime.time(0, 0, 0)) + data["eventtime"]
            self.sleep_id = data["sleepid"]
            self.log_id = data["logid"]
            self.start_time = data["startdatetime"]
            self.end_time = data["enddatetime"]
            self.timezone = data["timezone"]
            self.duration = data["duration"]
            self.main_sleep = data["mainsleep"]
        else:
            raise ValueError('Event id not found in database')

    def update_timezone(self, new_timezone):
        # convert utc time to "old" local
        local_datetime = common.utc_to_local(self.datetime, timezone=self.timezone)
        # take that "old" local and re-compute utc with "new" timezone
        self.datetime = common.local_to_utc(local_datetime.replace(tzinfo=None), timezone=new_timezone)
        self.timezone = new_timezone
        # store that in the db
        eventdb.update_fitbit_sleep_timezone(self.sleep_id, self.datetime.date(), self.datetime.time(), self.timezone)


def process_from_file(file_path):
    current_user = common.UserPreferences(1)
    process_dir = common.unpack_and_store_files(file_path)
    sleep_import = FitbitSleepImporter(process_dir)
    sleep_import.add_to_database(current_user)
    common.cleanup(process_dir)


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
