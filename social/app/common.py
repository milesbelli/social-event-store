from tracemalloc import start
import eventdb
import pytz
import datetime
import zipfile
import time
from pathlib import Path
import os
import hashlib


class UserPreferences:
    def __init__(self, user_id):
        self.user_id = user_id
        # Pull prefs from DB and then save them to object
        db_prefs = eventdb.get_user_preferences(self.user_id)
        self.timezone = db_prefs.get('timezone') or 'UTC'
        self.reverse_order = int(db_prefs.get('reverse_order') or 0)
        self.show_twitter = int(db_prefs.get("show_twitter") or 1)
        self.show_fitbit_sleep = int(db_prefs.get("show_fitbit-sleep") or 1)
        self.show_foursquare = int(db_prefs.get("show_foursquare") or 1)
        self.show_sms = int(db_prefs.get("show_sms") or 1)
        self.show_psn = int(db_prefs.get("show_psn") or 1)
        self.twitter_access_token = db_prefs.get("twtr_token") or None
        self.twitter_token_secret = db_prefs.get("twtr_secret") or None

    def update(self, **kwargs):
        # Update the items provided
        self.timezone = kwargs.get('timezone') or self.timezone
        self.reverse_order = int(kwargs.get('reverse_order') or self.reverse_order)
        eventdb.set_user_preferences(self.user_id,
                                     timezone=self.timezone,
                                     reverse_order=self.reverse_order)

    def save_filters(self, **kwargs):
        self.show_twitter = kwargs.get("show_twitter") or self.show_twitter
        self.show_fitbit_sleep = kwargs.get("show_fitbit-sleep") or self.show_fitbit_sleep
        self.show_foursquare = kwargs.get("show_foursquare") or self.show_foursquare
        self.show_sms = kwargs.get("show_sms") or self.show_sms
        self.show_psn = kwargs.get("show_psn") or self.show_psn
        eventdb.set_user_source_preferences(self.user_id, **kwargs)

    def get_filters(self):
        list_of_filters = list()

        if self.show_twitter == 1:
            list_of_filters.append("twitter")
        if self.show_fitbit_sleep == 1:
            list_of_filters.append("fitbit-sleep")
        if self.show_foursquare == 1:
            list_of_filters.append("foursquare")
        if self.show_sms == 1:
            list_of_filters.append("sms")
        if self.show_psn ==1:
            list_of_filters.append("psn")

        return list_of_filters


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
        event_dtime = datetime.datetime.combine(event["date"], datetime.time()) + event["time"]
        event_dtime = utc_to_local(event_dtime, timezone=user_prefs.timezone)

        event["date"] = event_dtime.date()
        # Handle either 24h or 12h time
        event_time = event_dtime.strftime('%I:%M:%S %p') if am_pm_time else event_dtime.time()

        event["time"] = event_time

    return events


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
        if not events_by_date.get(event["date"].strftime("%Y-%m-%d")):
            events_by_date[event["date"].strftime("%Y-%m-%d")] = []

        # Pass in the entire event as kwargs, eventObject will know how to build it
        social_event = eventObject(**event, user_prefs=user_prefs)

        # take the built eventObject and append to the day
        events_by_date[event["date"].strftime("%Y-%m-%d")].append(social_event)

    # Additionally store useful metadata like number of events for each day
    for day in list_of_days:
        day["events"] = events_by_date.get(day["date_full"]) or day["events"]
        day["count"] = len(day["events"])

    # performance measurement logging
    print(f"Got month of events parsed in {datetime.datetime.now() - start_time}")

    return list_of_days


def get_events_for_date_range(start_date, end_date, user_prefs=None, **kwargs):

    # Query the db for events of given type(s) and date range

    sources = kwargs.get("sources") or user_prefs.get_filters()

    if user_prefs:
        start_date, end_date = localize_date_range(start_date, end_date, timezone=user_prefs.timezone)

    output = eventdb.get_datetime_range(start_date, end_date, sources, user_prefs)

    return output


def get_conversation_page(conversation, page_size, start_dt=None, **kwargs):

    user_prefs = kwargs.get("preferences")

    # Start date is specified if we don't want to start at the top
    if not start_dt:
        start_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Increase size by 1 for next page
    page_size += 1

    # get SMS messages for the given conversation and convert to 
    messages = events_in_local_time(eventdb.get_conversation(conversation,
                                    start_dt, page_size, user_prefs),
                                    user_prefs, True)

    # Track what days we've seen so far
    messages_by_date = dict()
    # Dict of messages and metadata for single day
    day_messages = dict()
    # List of all day dicts, in the proper order
    days_in_order = list()

    # Undo back to UTC again for next page if exists
    if len(messages) == page_size:
        msg_dt = messages[-1]["date"].strftime("%Y-%m-%d") +\
                " " + messages[-1]["time"]
        next_dt = datetime.datetime.strptime(msg_dt, "%Y-%m-%d %I:%M:%S %p")
        next_dt = local_to_utc(next_dt, timezone=user_prefs.timezone)
        next_dt = next_dt.strftime("%Y-%m-%d %H:%M:%S")
        messages.pop()
    else:
        next_dt = None

    # Build all the above
    for message in messages:
        date_key = message["date"].strftime("%Y-%m-%d")
        if not messages_by_date.get(date_key):
            messages_by_date[date_key] = 1
            day_messages = dict()
            day_messages["messages"] = list()
            day_messages["date"] = date_key
            day_messages["date_human"] = \
                message["date"].strftime("%A, %B %d %Y")
            days_in_order.append(day_messages)

        days_in_order[-1]["messages"].append(eventObject(**message,
                                             user_prefs=user_prefs))

    # To avoid making another SQL query, we grab the title from the first
    # message in the list. But in edge cases where no number is found, we need
    # something to display

    conv_name = days_in_order[0]['messages'][0].get_title() if \
        len(days_in_order) > 0 else "No conversation found"

    return days_in_order, next_dt, conv_name


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


def unpack_and_store_files(zipfile_path, parent_directory=None, type=None):
    # Returns the temporary directory for the files that were extracted

    parent_directory = parent_directory or os.getenv("PATH_OUTPUT") or "output"
    create_directory(parent_directory)

    if zipfile.is_zipfile(zipfile_path):

        # Generate a unique foldername for storing output files
        # TODO: Make this more unique? A datetime string isn't unique enough
        directory_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        output_path = f"{parent_directory}/{directory_stamp}"

        Path.mkdir(Path(output_path))

        with zipfile.ZipFile(zipfile_path) as zipfile_to_process:
            for entry in zipfile_to_process.namelist():

                filename = entry.split("/")[-1]

                # Twitter tweet file
                if ("data/js/tweets" in entry and ".js" in entry) \
                   or (filename == "tweet.js"):
                    js_file_to_save = zipfile_to_process.read(entry)
                    output_file = open(f"{output_path}/{entry.split('/')[-1]}", "wb")
                    output_file.write(js_file_to_save)
                    output_file.close()

                # Twitter account file
                elif filename == "account.js":
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

                # Foursquare files
                elif "checkins" in entry and ".js" in entry:
                    checkin_file_to_save = zipfile_to_process.read(entry)
                    output_file = open(f"{output_path}/{entry.split('/')[-1]}", "wb")
                    output_file.write(checkin_file_to_save)
                    output_file.close()

                # SMS file
                elif type == "sms":
                    sms_file_to_save = zipfile_to_process.read(entry)
                    output_file = open(f"{output_path}/{entry.split('/')[-1]}", "wb")
                    output_file.write(sms_file_to_save)
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

        social_event = eventObject(**event)

        # Ever wonder how to get a datetime object out of a date and a timedelta? Wonder no more!
        start_time = datetime.datetime.combine(social_event.date, datetime.time()) + social_event.time

        event_date = str(social_event.date).replace('-', '')
        event_time = str(start_time.time()).replace(':', '')
        geocoordinates = f"GEO:{social_event.get_geo()['latitude']};{social_event.get_geo()['longitude']}\n"\
            if social_event.get_geo() else str()

        location = f"LOCATION:{social_event.ical_location()}\n" if social_event.ical_location() else str()

        event_title = social_event.ical_title()
        event_body = social_event.ical_body()

        end_datetime = start_time + datetime.timedelta(0, int(social_event.get_timedelta()) / 1000)
        date_end = str(end_datetime.date()).replace('-', '')
        time_end = str(end_datetime.time()).replace(':', '')

        ical_string += word_wrap(f"BEGIN:VEVENT\n"
                                 f"UID:{social_event.id}{time_now}@social-event-store\n"
                                 f"DTSTAMP:{date_now}T{time_now}Z\n"
                                 f"DTSTART:{event_date}T{event_time}Z\n"
                                 f"DTEND:{date_end}T{time_end}Z\n"
                                 f"{geocoordinates}"
                                 f"{location}"
                                 f"SUMMARY:{event_title}\n"
                                 f"DESCRIPTION:{event_body}\n"
                                 f"END:VEVENT\n")

    ical_string += "END:VCALENDAR"

    return ical_string


def create_directory(output_dir):

    directory_list = output_dir.split("/")
    directory_path = str()
    for i in range(0, len(directory_list)):

        directory_path += directory_list[i]

        if not Path(directory_path).exists():
            Path.mkdir(Path(directory_path))
            directory_path += "/"


def export_ical(events):

    # Output folder must be created, check for this
    output_dir = os.getenv("PATH_OUTPUT") or "output"
    create_directory(output_dir)

    ical_text = output_events_to_ical(events)
    output_path = f"{output_dir}/export_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.ics"

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


# Mama mía, that's a spicy optimization!!! The dict object created from the SQL query is imported directly into
# the eventObject as a bunch of kwargs. We get away with this because kwargs are just a dict to begin with and all the
# aliases map directly to those arguments. It's a thousand percent easier than before.
def convert_dict_to_event_objs(list_of_dicts, user_prefs):
    output_list = list()

    for event in list_of_dicts:
        social_event = eventObject(**event, user_prefs=user_prefs)
        output_list.append(social_event)

    return output_list


def get_previous_sms(conversation, start, length, user_prefs):

    prev = eventdb.get_previous_conversation(conversation, start, length,
                                             user_prefs)

    prev = prev[0]["eventdt"].strftime("%Y-%m-%d %H:%M:%S") if len(prev) > 0 \
        else None

    return prev


class eventObject:
    '''
    eventObject is a generic object which stores data for a single event. This can include:
        * timestamp - timestamp of event
        * title - the title of the event, if applicable; should be short and will appear bolded in UI
        * subtitle - an optional smaller subtitle which will appear beneath the title, in italics
        * body - main body of the event, should generally contain the most information with some exceptions
        * source_id - a unique id for the event from the source service, used if a view link is available
    '''
    def __init__(self, date, time, object_type, source_id,
                 user_prefs=None, **kwargs):

        self.type = object_type
        self.id = source_id
        self.date = date
        self.time = time
        self.prefs = user_prefs

        if self.type == "twitter":
            # set up Twitter fields
            self.body = kwargs.get("body")
            self.geo = {"latitude": kwargs.get("latitude"),
                        "longitude": kwargs.get("longitude")}
            self.reply_id = kwargs.get("reply_id")
            self.client = kwargs.get("client")

        elif self.type == "fitbit-sleep":
            # set up Fitbit fields
            # args needed:
            # sleep_time, rest_mins, start_time, end_time

            self.geo = None

            sleep_time = kwargs.get("sleep_time")
            rest_time = kwargs.get("rest_mins")
            self.start_time = kwargs.get("start_time")
            self.end_time = kwargs.get("end_time")
            self.timedelta = sleep_time

            self.timezone = kwargs.get("timezone")
            self.sleep_id = kwargs.get("sleep_id")

            if None in [sleep_time, rest_time, self.start_time, self.end_time]:
                raise ValueError("Required field missing. Required fields are sleep_time, rest_mins, start_time, end_time.")

            self.sleep_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(sleep_time)/1000)
            readable_time = self.sleep_time.strftime("%H hours, %M minutes")
            self.rest_time = datetime.datetime(1, 1, 1) + datetime.timedelta(0, int(rest_time) * 60)
            readable_rest = self.rest_time.strftime("%H hours, %M minutes")
            self.body = (f"Total time in bed: {readable_time} \n" +
                         f"Restful time: {readable_rest}\n" +
                         f"Local start time: {self.start_time.strftime('%B %d, at %I:%M %p')}\n" +
                         f"Local end time: {self.end_time.strftime('%B %d, at %I:%M %p')}")

        elif self.type == "foursquare":
            # Set up Swarm fields
            self.id = kwargs.get("checkin_id")
            self.body = kwargs.get("body") or ""
            self.geo = {"latitude": kwargs.get("latitude"),
                        "longitude": kwargs.get("longitude")}
            self.checkin_id = kwargs.get("checkin_id")
            self.venue_name = kwargs.get("venue_name")
            self.venue_event_name = kwargs.get("venue_event_name")
            self.address = kwargs.get("address")
            self.city = kwargs.get("city")
            self.state = kwargs.get("state")
            self.country = kwargs.get("country")
            self.venue_id = kwargs.get("venue_id")

        elif self.type == "sms":
            self.body = kwargs.get("body") or str()
            self.geo = None
            self.conversation = kwargs.get("conversation")
            self.contact = kwargs.get("contact_num")
            self.folder = kwargs.get("folder")
            self.contact_nm = kwargs.get("contact_name")

        elif self.type == "psn":
            self.body = kwargs.get("body") or str()
            self.trophy_name = kwargs.get("trophy_name")
            self.platform = kwargs.get("client")
            self.game_title = kwargs.get("game_title")
            self.trophy_type = kwargs.get("trophy_type")

            self.geo = None

        else:
            raise ValueError(f"Unsupported event type: {self.type}")

    def get_body(self):
        return self.body

    def get_footer(self):
        if self.type == "twitter":
            return f"via {self.client}"
        elif self.type == "fitbit-sleep":
            return f"in {self.timezone}"
        elif self.type == "foursquare":
            footer_list = list()
            for item in [self.city, self.state, self.country]:
                if item:
                    footer_list.append(item)
            return ", ".join(footer_list) if footer_list != [] \
                else "Location unknown"
        elif self.type == "sms":
            return f"from me" if self.folder == "outbox" else f"from {self.contact_nm or self.contact}"
        elif self.type == "psn":
            return f"{self.trophy_type} trophy for {self.platform}"

    def get_url(self):
        if self.type == "twitter":
            url = f"https://www.twitter.com/i/status/{self.id}/"
        elif self.type == "fitbit-sleep":
            url = f"https://www.fitbit.com/sleep/{self.end_time.strftime('%Y-%m-%d')}/{self.id}/"
        elif self.type == "foursquare":
            url = f"https://www.swarmapp.com/i/checkin/{self.checkin_id}/"
        elif self.type == "sms":
            url = f"/conversation/{self.conversation or self.contact}"
            if self.prefs is not None:
                local_dt = self.date.strftime("%Y-%m-%d") + " " + self.time
                utc_dt = datetime.datetime.strptime(local_dt,
                                                    "%Y-%m-%d %I:%M:%S %p")
                utc_dt = local_to_utc(utc_dt, timezone=self.prefs.timezone)
                url += f"?start={utc_dt}"
        else:
            url = "#"

        return url

    def get_reply_id(self):
        if self.type == "twitter":
            return self.reply_id or None
        else:
            return None

    def get_geo(self):
        if self.geo:
            return self.geo if self.geo["latitude"] and self.geo["longitude"] else None
        else:
            return None

    def fetch_venue(self):
        if self.type == "foursquare":
            return self.venue_id
        else:
            return None

    def is_editable(self):
        if self.type == "fitbit-sleep":
            return True
        else:
            return False

    def get_edit_url(self):
        if self.type == "fitbit-sleep":
            return f"/edit-sleep/{self.sleep_id}"
        else:
            return None

    def get_title(self):
        if self.type == "foursquare":
            return f"Checked in at {self.venue_name}"
        elif self.type == "sms":
            conversation = None
            if self.conversation:
                conversation = self.conversation.replace("~", ", ")
            return f"Conversation with {conversation or self.contact_nm or self.contact}"
        elif self.type == "psn":
            return f"🏆 {self.trophy_name}"
        else:
            return None

    def get_subtitle(self):
        if self.type == "foursquare" and self.venue_event_name:
            return f"for {self.venue_event_name}"
        elif self.type == "psn":
            return self.game_title
        else:
            return None

    def get_timedelta(self):
        if self.type == "fitbit-sleep":
            return self.timedelta
        else:
            return 0

    def get_type(self):
        if self.type == "sms":
            return f"{self.type} {'txtin' if self.folder == 'inbox' else 'txtout'}"
        else:
            return self.type

    def ical_title(self):
        if self.type == "twitter":
            return self.body.replace('\n', ' ').replace('\r', ' ')
        elif self.type == "fitbit-sleep":
            readable_rest = self.rest_time.strftime("%H hours, %M minutes")
            return f"Restful time: {readable_rest}"
        elif self.type == "foursquare":
            return f"{self.get_title()} {self.get_subtitle() or str()}"
        elif self.type == "psn":
            return f"🏆 {self.trophy_name} ({self.game_title})"

    def ical_body(self):
        output = self.body.replace('\n', '\\n').replace('\r', '\\n')
        if self.type == "twitter":
            output = f"{output}\\n\\n{self.get_url()} | {self.get_footer()}"
        return output

    def ical_location(self):
        if self.type == "foursquare":
            address_list = list()
            for item in [self.address, self.city, self.state, self.country]:
                if item:
                    address_list.append(item)
            return f"{', '.join(address_list)}" if address_list else self.venue_name
        else:
            return None

    def get_viewtext(self):
        if self.type == "sms":
            return "View Conversation"
        else:
            return "View Online"

    def get_hash(self):
        seed = "-".join([str(self.body), str(self.get_title()),
                        str(self.get_subtitle()), str(self.get_footer()),
                        str(self.date), str(self.time)])
        seed = seed.encode("utf-8")
        return hashlib.sha1(seed).hexdigest()
