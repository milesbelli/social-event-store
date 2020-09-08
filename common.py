import eventdb
import pytz
import datetime


class UserPreferences:
    def __init__(self, user_id):
        self.user_id = user_id
        db_prefs = eventdb.get_user_preferences(self.user_id)
        self.timezone = db_prefs.get('timezone') or 'UTC'
        self.reverse_order = int(db_prefs.get('reverse_order') or 0)

    def update(self, **kwargs):
        self.timezone = kwargs.get('timezone') or self.timezone
        self.reverse_order = kwargs.get('reverse_order')
        eventdb.set_user_preferences(1,
                                     timezone=self.timezone,
                                     reverse_order=self.reverse_order)


def utc_to_local(source_dt, **kwargs):
    # Use pytz module to convert a utc datetime to local datetime

    timezone = kwargs.get("timezone")

    utc = pytz.timezone("utc")
    local = pytz.timezone(timezone)

    utc_dt = utc.localize(source_dt)
    return utc_dt.astimezone(local)


def local_to_utc(source_dt, **kwargs):
    # Use pytz module to convert a local datetime to utc datetime

    timezone = kwargs.get("timezone") or 'UTC'

    local = pytz.timezone(timezone)
    utc = pytz.timezone("utc")

    local_dt = local.localize(source_dt)
    return local_dt.astimezone(utc)


def events_in_local_time(events, user_prefs, am_pm_time=False):

    output_events = list()

    for event in events:
        event_dtime = datetime.datetime.combine(event[0], datetime.time()) + event[1]
        event_dtime = utc_to_local(event_dtime, timezone=user_prefs.timezone)

        event_out = list()
        event_out.append(event_dtime.date())
        event_time = event_dtime.strftime('%I:%M:%S %p') if am_pm_time else event_dtime.time()
        event_out.append(event_time)

        for i in range(2, len(event)):
            event_out.append(event[i])

        output_events.append(event_out)

    return output_events


def get_one_month_of_events(year, month, **kwargs):

    user_prefs = kwargs.get("preferences") or UserPreferences(1)

    start_time = datetime.datetime.now()

    day_of_month = datetime.date(year, month, 1)
    first_day = day_of_month.strftime("%Y-%m-%d")
    list_of_days = list()

    while day_of_month.month == month:
        str_date = day_of_month.strftime("%Y-%m-%d")
        today = dict()
        today["date_human"] = day_of_month.strftime("%A, %B %d %Y")
        today["date_full"] = str_date
        today["date_day"] = str(day_of_month.day)
        today["events"] = []
        today["count"] = len(today["events"])
        last_day = str_date

        list_of_days.append(today)
        day_of_month = day_of_month + datetime.timedelta(1, 0)

    events = events_in_local_time(get_events_for_date_range(first_day, last_day, user_prefs),
                                  user_prefs, True)
    events_by_date = dict()
    for event in events:
        if not events_by_date.get(event[0].strftime("%Y-%m-%d")):
            events_by_date[event[0].strftime("%Y-%m-%d")] = []

        # Fitbit Sleep specific modifications
        if event[7] == "fitbit-sleep":
            sleep_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(event[3])/1000)
            readable_time = sleep_time.strftime("%H hours, %M minutes")
            event[3] = f"Fell asleep for {readable_time} - ended on {event[8].strftime('%B %d, at %I:%M %p')}"

        events_by_date[event[0].strftime("%Y-%m-%d")].append(event)

    for day in list_of_days:
        day["events"] = events_by_date.get(day["date_full"]) or day["events"]
        day["count"] = len(day["events"])

    print(f"Got month of events parsed in {datetime.datetime.now() - start_time}")

    return list_of_days


def get_events_for_date_range(start_date, end_date, user_prefs=None):

    if user_prefs:
        start_date, end_date = localize_date_range(start_date, end_date, timezone=user_prefs.timezone)

    output = eventdb.get_datetime_range(start_date, end_date, ["twitter", "fitbit-sleep"])

    return output


def localize_date_range(start_date, end_date, **kwargs):
    # First convert the str dates to datetime dates
    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")

    # Then add times to be datetime objects
    start_date = datetime.datetime.combine(start_date, datetime.time(0, 0))
    end_date = datetime.datetime.combine(end_date, datetime.time(23, 59, 59))

    # Then go from Local to UTC
    timezone = kwargs.get('timezone') or 'UTC'
    start_date = local_to_utc(start_date, timezone=timezone)
    end_date = local_to_utc(end_date, timezone=timezone)

    # Finally back to strings
    start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')

    return start_date, end_date
