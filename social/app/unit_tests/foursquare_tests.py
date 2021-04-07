import unittest
import foursquare as f
import datetime as dt
import pytz as tz
import common as c


class MyTestCase(unittest.TestCase):
    def test_foursquare_init(self):
        # You must create a folder inside data directory call fsq_test
        all_checkins = f.foursquareImporter('../data/fsq_test/')
        first_checkin = all_checkins.checkins.popitem()[1]

        self.assertEqual(first_checkin["venue"]["name"], "Bareburger")
        self.assertEqual(dt.datetime(2021,1,4,1,4,17, tzinfo=tz.timezone("UTC")),
                         dt.datetime.fromtimestamp(first_checkin["createdAt"], tz.timezone("UTC")))
        self.assertEqual(first_checkin.get_datetime(), dt.datetime(2021,1,4,1,4,17, tzinfo=tz.timezone("UTC")))
        self.assertEqual(first_checkin.get_date(), dt.date(2021,1,4))
        self.assertEqual(first_checkin.get_time(), dt.time(1,4,17))
        self.assertEqual(first_checkin.get_time_str(), "01:04:17")
        self.assertEqual(first_checkin.get_date_str(), "2021-01-04")

    def test_foursquare_add_to_db(self):
        all_checkins = f.foursquareImporter('../data/fsq_test/')

        my_user = c.UserPreferences(1)
        all_checkins.add_to_database(my_user)




if __name__ == '__main__':
    unittest.main()
