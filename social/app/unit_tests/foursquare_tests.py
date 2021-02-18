import unittest
import foursquare as f
import datetime as dt
import pytz as tz


class MyTestCase(unittest.TestCase):
    def test_foursquare_init(self):
        # You must create a folder inside data directory call fsq_test
        all_checkins = f.foursquareImporter('../data/fsq_test/')
        first_checkin = all_checkins.checkin_list[0]

        self.assertEqual(first_checkin["venue"]["name"], "Bareburger")
        self.assertEqual(dt.datetime(2021,1,4,1,4,17, tzinfo=tz.timezone("UTC")),
                         dt.datetime.fromtimestamp(first_checkin["createdAt"], tz.timezone("UTC")))
        self.assertEqual(first_checkin.get_datetime(), dt.datetime(2021,1,4,1,4,17, tzinfo=tz.timezone("UTC")))

if __name__ == '__main__':
    unittest.main()
