import unittest
import eventdb as db
import common as c


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

    def test_change_time(self):
        user_prefs = c.UserPreferences(1)
        event_id = "7572"
        new_date = "1970-06-01"
        new_time = "12:30:59"
        event_type = "sms"

        db.edit_timestamp_for_event(event_id, event_type, new_time, new_date, user_prefs)

        newer_date = "1970-12-31"
        newer_time = "23:59:59"

        db.edit_timestamp_for_event(event_id, event_type, newer_time, newer_date, user_prefs)


if __name__ == '__main__':
    unittest.main()
