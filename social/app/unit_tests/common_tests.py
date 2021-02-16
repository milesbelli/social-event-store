import unittest
import common as c
import datetime as dt


class MyTestCase(unittest.TestCase):
    def test_fitbit_eventobj_init(self):
        tstmp = dt.datetime.now()
        strt = dt.datetime(2012, 1, 1, 18, 30, 49)
        end = dt.datetime(2012, 1, 2, 6, 50, 49)
        myobj = c.eventObject(tstmp.date(), dt.timedelta(0, 12345), 'fitbit-sleep', 123456789, sleep_time='285000', rest_mins=50,
                              start_time=strt, end_time=end)

        self.assertEqual(type(myobj), c.eventObject)
        self.assertEqual(myobj.type, "fitbit-sleep")
        self.assertEqual(myobj.date, tstmp.date())
        self.assertEqual(myobj.time, dt.timedelta(0, 12345))
        self.assertEqual(type(myobj.date), dt.date)
        self.assertEqual(type(myobj.time), dt.timedelta)
        self.assertGreater(len(myobj.body), 1)

    def test_bad_eventjob_init(self):
        def setup_function():
            myobj = c.eventObject(dt.date(2001, 1, 1), dt.timedelta(0, 2000), "bad-type", 1001)
        self.assertRaises(ValueError, setup_function)


if __name__ == '__main__':
    unittest.main()
