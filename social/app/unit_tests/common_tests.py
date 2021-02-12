import unittest
import common as c
import datetime as dt


class MyTestCase(unittest.TestCase):
    def test_eventobj_init(self):
        tstmp = dt.datetime.now()
        strt = dt.datetime(2012, 1, 1, 18, 30, 49)
        end = dt.datetime(2012, 1, 2, 6, 50, 49)
        myobj = c.eventObject(tstmp, 'fitbit-sleep', 123456789, sleep_time='285000', rest_mins=50, start_time=strt,
                              end_time=end)

        self.assertEqual(type(myobj), c.eventObject)
        self.assertEqual(myobj.type, "fitbit-sleep")
        self.assertEqual(myobj.timestamp, tstmp)
        self.assertEqual(type(myobj.timestamp), dt.datetime)
        self.assertGreater(len(myobj.body), 1)


if __name__ == '__main__':
    unittest.main()
