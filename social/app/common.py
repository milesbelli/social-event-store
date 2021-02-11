import eventdb
import pytz
import datetime
import zipfile
import time
from pathlib import Path


class UserPreferences:
    def __init__(self, user_id):
        self.user_id = user_id
        # Pull prefs from DB and then save them to object
        db_prefs = eventdb.get_user_preferences(self.user_id)
        self.timezone = db_prefs.get('timezone') or 'UTC'
        self.reverse_order = int(db_prefs.get('reverse_order') or 0)

    def update(self, **kwargs):
        # Update the items provided
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

    # Loop through list of events and change all times to local

    output_events = list()

    for event in events:
        event_dtime = datetime.datetime.combine(event[0], datetime.time()) + event[1]
        event_dtime = utc_to_local(event_dtime, timezone=user_prefs.timezone)

        # All columns in event will be stored in this list
        event_out = list()
        # Append the date to the list
        event_out.append(event_dtime.date())
        # Handle either 24h or 12h time
        event_time = event_dtime.strftime('%I:%M:%S %p') if am_pm_time else event_dtime.time()
        # Append the time to the list
        event_out.append(event_time)

        # Append all successive items to the list
        for i in range(2, len(event)):
            event_out.append(event[i])

        # Append whole event to the list
        output_events.append(event_out)

    return output_events


def get_one_month_of_events(year, month, **kwargs):

    user_prefs = kwargs.get("preferences") or UserPreferences(1)

    # for performance logging
    start_time = datetime.datetime.now()

    # Create a datetime object for the first of the given month
    day_of_month = datetime.date(year, month, 1)
    first_day = day_of_month.strftime("%Y-%m-%d")
    # Create the list to use
    list_of_days = list()

    # Advance through the month one day at a time and build the object to store the events
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

    # Now that the object is built, query DB for all events for the time range
    events = events_in_local_time(get_events_for_date_range(first_day, last_day, user_prefs),
                                  user_prefs, True)

    # Populate a dict with dates as keys, and a list of the events as values
    events_by_date = dict()
    for event in events:
        # Add a date as key if not already in the dict
        if not events_by_date.get(event[0].strftime("%Y-%m-%d")):
            events_by_date[event[0].strftime("%Y-%m-%d")] = []

        # Fitbit Sleep specific modifications
        if event[7] == "fitbit-sleep":
            sleep_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(event[3])/1000)
            readable_time = sleep_time.strftime("%H hours, %M minutes")
            rest_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(event[10]) * 60)
            readable_rest = rest_time.strftime("%H hours, %M minutes")
            event[3] = (f"Total time in bed: {readable_time} \n"
                        f"Restful time: {readable_rest}\n"
                        f"Local start time: {event[11].strftime('%B %d, at %I:%M %p')}\n"
                        f"Local end time: {event[8].strftime('%B %d, at %I:%M %p')}")

        events_by_date[event[0].strftime("%Y-%m-%d")].append(event)

    # Additionally store useful metadata like number of events for each day
    for day in list_of_days:
        day["events"] = events_by_date.get(day["date_full"]) or day["events"]
        day["count"] = len(day["events"])

    # performance measurement logging
    print(f"Got month of events parsed in {datetime.datetime.now() - start_time}")

    return list_of_days


def get_events_for_date_range(start_date, end_date, user_prefs=None, **kwargs):

    # Query the db for events of given type(s) and date range

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

        # Generate a unique foldername for storing output files
        # TODO: Make this more unique? A datetime string isn't unique enough
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
                elif "sleep-" in entry and ".js" in entry:
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

    print(f"[{datetime.datetime.now()}] Received request to delete {to_delete}...")

    max_attempts = 12
    attempts = 0
    deleted = False

    # Cute little function to recursively delete all files in a directory since a directory must be
    # empty before it can be deleted for some reason
    def delete_dir(dir_path):
        for file in dir_path.iterdir():
            if file.is_file():
                file.unlink()
                print(f"[{datetime.datetime.now()}] Deleted {file}")
            elif Path(file).is_dir():
                delete_dir(Path(file))
        dir_path.rmdir()
        print(f"[{datetime.datetime.now()}] Deleted {dir_path}")

    while attempts < max_attempts and not deleted:
        try:
            target_path = Path(to_delete)
            if target_path.is_dir():
                delete_dir(target_path)
            else:
                target_path.unlink()
                print(f"[{datetime.datetime.now()}] Deleted {target_path}")

            deleted = True

        except OSError:
            print(f"[{datetime.datetime.now()}] Could not delete {to_delete}, file is busy.")
            time.sleep(5)

        attempts += 1


def output_events_to_ical(list_of_events):

    # Hardcoding required iCal file formatting
    ical_string = ("BEGIN:VCALENDAR\nVERSION:2.0\n"
                   "PRODID:-//Louis Mitas//social-event-store 1.0.0//EN\n")

    time_now = str(datetime.datetime.now().time()).replace(":", "")[:6]
    date_now = str(datetime.datetime.now().date()).replace("-", "")

    for event in list_of_events:

        # Ever wonder how to get a datetime object out of a date and a timedelta? Wonder no more!
        start_time = datetime.datetime.combine(event[0], datetime.time()) + event[1]

        # Event date and time are fairly universal by design, and that's about it
        event_date = str(event[0]).replace('-', '')
        event_time = str(start_time.time()).replace(':', '')

        # Constructing ical event for Twitter
        if event[7] == "twitter":
            geocoordinates = f"GEO:{event[5]};{event[6]}\n" if event[5] else str()

            event_title = event[3].replace('\n', ' ').replace('\r', ' ')
            event_body = event[3].replace('\n', '\\n').replace('\r', '\\n')

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

        # Constructing ical event for Fitbit sleep events
        elif event[7] == "fitbit-sleep":

            sleep_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(event[3])/1000)
            end_datetime = start_time + datetime.timedelta(0, int(event[3])/1000)
            readable_time = sleep_time.strftime("%H hours, %M minutes")
            rest_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(event[10]) * 60)
            readable_rest = rest_time.strftime("%H hours, %M minutes")
            date_end = str(end_datetime.date()).replace('-', '')
            time_end = str(end_datetime.time()).replace(':', '')

            title_text = f"Restful time: {readable_rest}"
            body_text = (f"Total time in bed: {readable_time}\\n"
                         f"Restful time: {readable_rest}\\n"
                         f"Local start time: {event[11].strftime('%B %d, at %I:%M %p')}\\n"
                         f"Local end time: {event[8].strftime('%B %d, at %I:%M %p')}")

            ical_string += word_wrap(f"BEGIN:VEVENT\n"
                                     f"UID:{event[2]}{time_now}@social-event-store\n"
                                     f"DTSTAMP:{date_now}T{time_now}Z\n"
                                     f"DTSTART:{event_date}T{event_time}Z\n"
                                     f"DTEND:{date_end}T{time_end}Z\n"
                                     f"SUMMARY:{title_text}\n"
                                     f"DESCRIPTION:{body_text}\n"
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


# iCal requires a file not contain any line longer than 75 octets which I realize is not the same thing as characters,
# so this might need to be enhanced later to support that, but for right now this is to handle that requirement
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


class eventObject:
    '''
    eventObject is a generic object which stores data for a single event. This can include:
        * timestamp - timestamp of event
        * title - the title of the event, if applicable; should be short and will appear bolded in UI
        * subtitle - an optional smaller subtitle which will appear beneath the title, in italics
        * body - main body of the event, should generally contain the most information with some exceptions
        * source_id - a unique id for the event from the source service, used if a view link is available
    '''
    def __init__(self, timestamp, object_type, source_id, **kwargs):

        if type(timestamp) is not datetime.datetime:
            raise TypeError("timestamp not in format datetime.datetime")

        if object_type == "twitter":
            # set up Twitter fields
            self.timestamp = timestamp
            self.id = source_id
            self.body = kwargs.get("body")
            self.geo = {"latitude": kwargs.get("latitude"),
                        "longitude": kwargs.get("longitude")}
            self.reply_id = kwargs.get("reply_id")
            self.client = kwargs.get("client")


        elif object_type == "fitbit-sleep":
            # set up Fitbit fields
            # args needed:
            # sleep_time, rest_mins, start_time, end_time

            sleep_time = kwargs.get("sleep_time")
            rest_time = kwargs.get("rest_mins")
            start_time = kwargs.get("start_time")
            end_time = kwargs.get("end_time")

            self.timezone = kwargs.get("timezone")
            self.timestamp = timestamp

            if None in [sleep_time, rest_time, start_time, end_time]:
                raise ValueError("Required field missing. Required fields are sleep_time, rest_mins, start_time, end_time.")

            sleep_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(sleep_time)/1000)
            readable_time = sleep_time.strftime("%H hours, %M minutes")
            rest_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(rest_time) * 60)
            readable_rest = rest_time.strftime("%H hours, %M minutes")
            self.body = (f"Total time in bed: {readable_time} \n" +
                         f"Restful time: {readable_rest}\n" +
                         f"Local start time: {start_time.strftime('%B %d, at %I:%M %p')}\n" +
                         f"Local end time: {end_time.strftime('%B %d, at %I:%M %p')}")

        elif object_type == "swarm":
            # Set up Swarm fields
            pass
        else:
            raise ValueError(f"Unsupported event type: {object_type}")
