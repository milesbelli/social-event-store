import unittest
import eventdb as db
import common as c
import json


class MyTestCase(unittest.TestCase):
    def test_update_contact(self):
        user_prefs = c.UserPreferences(1)
        contact_info = {"contact_name": "test", "contact_num": "+15559991234"}
        db.edit_contact(contact_info, user_prefs)

        contact_sql = f"SELECT * from sms_contacts WHERE contact_name = '{contact_info['contact_name']}'" \
                      f" AND contact_num = '{contact_info['contact_num']}' AND userid = '{user_prefs.user_id}';"

        results = db.get_results_for_query(contact_sql)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["contact_name"], "test")

    # def test_change_time(self):
    #     user_prefs = c.UserPreferences(1)
    #     event_id = "7572"
    #     new_date = "1970-06-01"
    #     new_time = "12:30:59"
    #     event_type = "sms"
    #
    #     db.edit_timestamp_for_event(event_id, event_type, new_time, new_date, user_prefs)
    #
    #     newer_date = "1970-12-31"
    #     newer_time = "23:59:59"
    #
    #     db.edit_timestamp_for_event(event_id, event_type, newer_time, newer_date, user_prefs)

    def test_insert_and_delete_fitbit_data(self):
        # User 0 is for the Test User, so we can store stuff in here without harming real user data
        user_prefs = c.UserPreferences(0)

        # Open sample file, contains one entry
        fitbit_file = open("unit_tests/sample_data/fitbit-sleep.json", "r")
        fitbit_list = json.loads(fitbit_file.read())
        fitbit_file.close()

        # Perform actual insert using sample file
        db.insert_fitbit_sleep(fitbit_list, user_prefs)

        insert_check_sql = f"SELECT sleepid, logid FROM fitbit_sleep WHERE logid = {fitbit_list[0]['logId']}" \
                           f" AND userid = {user_prefs.user_id};"

        results = db.get_results_for_query(insert_check_sql)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["logid"], 32332925893)

        id_to_delete = results[0]["sleepid"]

        db.delete_item_from_db(id_to_delete, "fitbit-sleep")

        results = db.get_results_for_query(insert_check_sql)

        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    unittest.main()
