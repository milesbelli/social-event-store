import unittest
import eventdb as db
import common as c
import sms as s
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

    def test_1_insert_fitbit_data(self):
        # User 0 is for the Test User, so we can store stuff in here without harming real user data

        print("Performing TEST 1")

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

    def test_2_delete_fitbit_data(self):

        print("Performing TEST 2")

        user_prefs = c.UserPreferences(0)
        insert_check_sql = f"SELECT sleepid, logid FROM fitbit_sleep WHERE logid = 32332925893" \
                           f" AND userid = {user_prefs.user_id};"

        results = db.get_results_for_query(insert_check_sql)

        id_to_delete = results[0]["sleepid"]

        db.delete_item_from_db(id_to_delete, "fitbit-sleep")

        results = db.get_results_for_query(insert_check_sql)

        self.assertEqual(len(results), 0)

    def test_3_insert_sms(self):

        print("Performing TEST 3")

        user_prefs = c.UserPreferences(0)

        smsfile = open("unit_tests/sample_data/sms.json")
        sms_data = json.loads(smsfile.read())
        smsfile.close()

        sms_dict = dict()

        for sms in sms_data:
            sms_dict[sms["id"]] = s.SmsMessage(**sms)

        db.insert_sms_into_db(sms_dict, user_prefs)

        sms_sql = f"SELECT * FROM sms_messages WHERE userid = {user_prefs.user_id};"
        results = db.get_results_for_query(sms_sql)

        self.assertEqual(len(results), 4)

    def test_4_change_sms_time(self):

        print("Performing TEST 4")

        user_prefs = c.UserPreferences(0)

        sms_sql = f"SELECT * FROM sms_messages s " \
                  f"LEFT JOIN events e ON e.detailid = s.smsid " \
                  f"WHERE e.userid = {user_prefs.user_id} AND " \
                  f"fingerprint = '05dfba83b9a2629dbb297c5279a3b4d211ade7b1';"
        results = db.get_results_for_query(sms_sql)

        old_dt = str(results[0]["eventdate"])
        old_tm = str(results[0]["eventtime"])

        db.edit_timestamp_for_event(str(results[0]["smsid"]), "sms", "13:25:49", "2015-05-26", user_prefs)

        results = db.get_results_for_query(sms_sql)

        self.assertNotEqual(old_tm, str(results[0]["eventtime"]))
        self.assertNotEqual(old_dt, str(results[0]["eventdate"]))

        self.assertEqual(str(results[0]["eventtime"]), "13:25:49")

    def test_5_delete_several_sms(self):

        print("Performing TEST 5")
        user_prefs = c.UserPreferences(0)

        sms_sql = f"SELECT smsid FROM sms_messages " \
                  f"WHERE userid = '{user_prefs.user_id}'"

        all_sms_ids = db.get_results_for_query(sms_sql)

        for sms_id in all_sms_ids:
            db.delete_item_from_db(sms_id["smsid"], "sms")

        count_sql = f"SELECT count(*) FROM sms_messages " \
                    f"WHERE userid = '{user_prefs.user_id}'"

        count = db.get_results_for_query(count_sql)

        self.assertEqual(count[0]["count(*)"], 0)


if __name__ == '__main__':
    unittest.main()
