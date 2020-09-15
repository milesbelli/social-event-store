import eventdb
import pytz
import datetime
import zipfile
import time
from pathlib import Path


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


def get_events_for_date_range(start_date, end_date, user_prefs=None, **kwargs):

    sources = kwargs.get("sources") or ["twitter", "fitbit-sleep"]

    if user_prefs:
        start_date, end_date = localize_date_range(start_date, end_date, timezone=user_prefs.timezone)

    output = eventdb.get_datetime_range(start_date, end_date, sources)

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


def unpack_and_store_files(zipfile_path, parent_directory):
    # Returns the temporary directory for the files that were extracted

    if not Path(parent_directory).exists():
        Path.mkdir(Path(parent_directory))

    if zipfile.is_zipfile(zipfile_path):

        directory_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        output_path = f"{parent_directory}/{directory_stamp}"

        Path.mkdir(Path(output_path))

        with zipfile.ZipFile(zipfile_path) as zipfile_to_process:
            for entry in zipfile_to_process.namelist():

                # Twitter tweet file
                if ("data/js/tweets" in entry and ".js" in entry) or ("tweet.js" in entry):
                    js_file_to_save = zipfile_to_process.read(entry)
                    output_file = open(f"{output_path}/{entry.split('/')[-1]}", "wb")
                    output_file.write(js_file_to_save)
                    output_file.close()

                # Twitter account file
                elif "account.js" in entry:
                    account_js = zipfile_to_process.read(entry)
                    Path.mkdir(Path(f"{output_path}/acct"))
                    output_acct = open(f"{output_path}/acct/account.js", "wb")
                    output_acct.write(account_js)
                    output_acct.close()

                # Fitbit sleep file
                elif "sleep-" in entry:
                    sleep_file_to_save = zipfile_to_process.read(entry)
                    output_file = open(f"{output_path}/{entry.split('/')[-1]}", "wb")
                    output_file.write(sleep_file_to_save)
                    output_file.close()

        cleanup(zipfile_path)

        return output_path


def cleanup(to_delete):
    # This probably would not have been needed on Unix. Windows locks
    # files in such a way that they cannot be flagged for deleting at a
    # later time, so the workaround is to keep trying in a daemon until
    # the file lock is released.

    print(f"Received request to delete {to_delete}...")

    max_attempts = 12
    attempts = 0
    deleted = False

    def delete_dir(dir_path):
        for file in dir_path.iterdir():
            if file.is_file():
                file.unlink()
                print(f"Deleted {file}")
            elif Path(file).is_dir():
                delete_dir(Path(file))
        dir_path.rmdir()
        print(f"Deleted {dir_path}")

    while attempts < max_attempts and not deleted:
        try:
            target_path = Path(to_delete)
            if target_path.is_dir():
                delete_dir(target_path)
            else:
                target_path.unlink()
                print(f"Deleted {target_path}")

            deleted = True

        except OSError:
            print(f"Could not delete {to_delete}, file is busy.")

        attempts += 1
        time.sleep(5)


def output_events_to_ical(list_of_events):

    ical_string = ("BEGIN:VCALENDAR\nVERSION:2.0\n"
                   "PRODID:-//Louis Mitas//social-event-store 1.0.0//EN\n")

    time_now = str(datetime.datetime.now().time()).replace(":", "")[:6]
    date_now = str(datetime.datetime.now().date()).replace("-", "")

    for event in list_of_events:

        # Ever wonder how to get a datetime object out of a date and a timedelta? Wonder no more!
        start_time = datetime.datetime.combine(event[0], datetime.time()) + event[1]

        if event[7] == "twitter":
            geocoordinates = f"GEO:{event[5]};{event[6]}\n" if event[5] else str()

            event_title = event[3].replace('\n', ' ').replace('\r', ' ')
            event_body = event[3].replace('\n', '\\n').replace('\r', '\\n')
            event_date = str(event[0]).replace('-', '')
            event_time = str(start_time.time()).replace(':', '')

            ical_string += word_wrap(f"BEGIN:VEVENT\n"
                                     f"UID:{event[2]}{time_now}@social-event-store\n"
                                     f"DTSTAMP:{date_now}T{time_now}Z\n"
                                     f"DTSTART:{event_date}T{event_time}Z\n"
                                     f"DTEND:{event_date}T{event_time}Z\n"
                                     f"{geocoordinates}"
                                     f"SUMMARY:{event_title}\n"
                                     f"DESCRIPTION:{event_body}"
                                     f"\\n\\nhttps://twitter.com/i/status/{event[2]} | via {event[4]}\n"
                                     f"END:VEVENT\n")

        elif event[7] == "fitbit-sleep":

            event_date = str(event[0]).replace('-', '')
            event_time = str(start_time.time()).replace(':', '')
            sleep_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(event[3])/1000)
            end_datetime = start_time + datetime.timedelta(0, int(event[3])/1000)
            readable_time = sleep_time.strftime("%H hours, %M minutes")
            date_end = str(end_datetime.date()).replace('-', '')
            time_end = str(end_datetime.time()).replace(':', '')

            ical_string += word_wrap(f"BEGIN:VEVENT\n"
                                     f"UID:{event[2]}{time_now}@social-event-store\n"
                                     f"DTSTAMP:{date_now}T{time_now}Z\n"
                                     f"DTSTART:{event_date}T{event_time}Z\n"
                                     f"DTEND:{date_end}T{time_end}Z\n"
                                     f"SUMMARY:Fell asleep for {readable_time}\n"
                                     f"END:VEVENT\n")

    ical_string += "END:VCALENDAR"

    return ical_string


def export_ical(events):

    # Output folder must be created, check for this
    if not Path("output").exists():
        Path.mkdir(Path("output"))

    ical_text = output_events_to_ical(events)
    output_path = f"output/export_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.ics"

    with open(output_path, "w", encoding="utf8") as ics_file:
        ics_file.write(ical_text)

    return output_path


def word_wrap(text_to_format):
    formatted_text = str()

    lines_list = text_to_format.split('\n')

    for line in lines_list:
        cursor = 0
        while cursor < len(line):
            curstart = cursor
            offset = 74 if formatted_text[-2:] == "\n " else 75
            cursor = cursor + offset if cursor + offset < len(line) else len(line)
            formatted_text = formatted_text + line[curstart:cursor] + "\n " \
                if cursor < len(line) else formatted_text + line[curstart:cursor]
        formatted_text += "\n"

    return formatted_text[:-1]
