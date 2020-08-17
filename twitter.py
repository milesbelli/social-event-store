import urllib.request
import json
import datetime
import eventdb
from pathlib import Path
import pytz
import zipfile
from multiprocessing import Process
import time
import requests


def retrieve_from_twitter(post_id):

    tweet_url = "https://twitter.com/milesbelli/status/" + str(post_id)
    tweet_page = urllib.request.urlopen(tweet_url)
    data = tweet_page.read()
    text = data.decode("utf-8")
    offset = text.find("\"metadata\">")
    time_stamp = text[offset+22:offset+44]
    time_stamp = time_stamp[0:time_stamp.find("<")]

    # This time is always going to be San Francisco time
    return time_stamp


def parse_js_text(text, acct=0):

    tweets_text = text[text.index('[ {'):]
    list_of_tweets = json.loads(tweets_text)

    # Twitter has once again changed how tweet.js is structured, so first check if we have to "unwrap" the tweet
    for i in range(0, len(list_of_tweets)):
        list_of_tweets[i] = list_of_tweets[i].get("tweet") or list_of_tweets[i]

    # Format for database
    for tweet_details in list_of_tweets:

        tweet_details = tweet_details.get("tweet") or tweet_details

        # Get all the metadata we're looking for
        tweet_timestamp = parse_date_time(tweet_details["created_at"])

        tweet_details["sql_date"] = str(tweet_timestamp.date())
        tweet_details["sql_time"] = str(tweet_timestamp.time())

        tweet_details["client_name"] = get_client_name(tweet_details["source"])

        tweet_details["text"] = tweet_details.get("text") or tweet_details.get("full_text")
        tweet_details["text"] = fix_symbols(tweet_details["text"])

        tweet_details["user"] = tweet_details.get("user") or {"id": acct}

        geo_data = tweet_details.get("geo") or {"geo": []}

        tweet_details["latitude"] = "{}".format(geo_data.get("coordinates", ["NULL"])[0])
        tweet_details["longitude"] = "{}".format(geo_data.get("coordinates", ["", "NULL"])[1])

        tweet_details["in_reply_to_status_id"] = tweet_details.get("in_reply_to_status_id") or "NULL"

        retweet = tweet_details.get("retweeted_status") or None
        rt_text = retweet["text"] if retweet else None
        tweet_details["rt_id"] = retweet["id_str"] if retweet else "NULL"

    return list_of_tweets


def get_account_id(file_path):
    with open(file_path) as acct:

        acct = acct.read()
        acct_text = acct[acct.index('[ {'):]
        acct_json = json.loads(acct_text)

        return acct_json[0]['account']['accountId']


def parse_date_time(raw_stamp):
    
    if raw_stamp[0:4].isnumeric():

        # Recent format, not used in newest archive
        yr = int(raw_stamp[0:4])
        mo = int(raw_stamp[5:7])
        dy = int(raw_stamp[8:10])
        hr = int(raw_stamp[11:13])
        mn = int(raw_stamp[14:16])
        sc = int(raw_stamp[17:19])
        
    elif raw_stamp[0:3].isalpha():

        # New format === older format
        yr = int(raw_stamp[26:30])
        mo = number_month(raw_stamp[4:7])
        dy = int(raw_stamp[8:10])
        hr = int(raw_stamp[11:13])
        mn = int(raw_stamp[14:16])
        sc = int(raw_stamp[17:19])
        
    return datetime.datetime(yr, mo, dy, hour=hr, minute=mn, second=sc)
    

def number_month(month_str):
    
    month_str = month_str.capitalize()

    months = {"Jan": 1,
              "Feb": 2,
              "Mar": 3,
              "Apr": 4,
              "May": 5,
              "Jun": 6,
              "Jul": 7,
              "Aug": 8,
              "Sep": 9,
              "Oct": 10,
              "Nov": 11,
              "Dec": 12
    }

    return months[month_str[0:3]]


def get_client_name(client_string):
    try:
        start_pos = client_string.index('>') + 1
        end_pos = client_string.index('<', start_pos)
    
        return client_string[start_pos:end_pos]
    
    except:
        return client_string
    

def process_directory(dir_path, acct=None):
    
    target_dir = Path(dir_path)
    list_of_tweets = list()
    
    cnx = eventdb.create_connection('social')

    if not acct:
        acct = get_account_id(f"{dir_path}/acct/account.js") if Path(f"{dir_path}/acct/account.js").exists() else None
    
    for target_file in target_dir.iterdir():

        if target_file.is_file():
            with open(target_file, "r", errors="replace") as file:

                file = file.read()
                list_of_tweets += parse_js_text(file, acct)

    eventdb.insert_tweets(list_of_tweets, cnx)
    eventdb.close_connection(cnx)

    cleanup(dir_path)


def process_from_file(file_path):

    process_dir = unpack_and_store_files(file_path, "output")
    process_directory(process_dir)

    
def get_one_tweet(tweetid):

    output = eventdb.get_tweet(tweetid)

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


def get_tweets_for_date_range(start_date, end_date, user_prefs=None):

    if user_prefs:
        start_date, end_date = localize_date_range(start_date, end_date, timezone=user_prefs.timezone)

    output = eventdb.get_datetime_range(start_date, end_date)

    return output


def get_count_for_date_range(start_date, end_date):

    start_date, end_date = localize_date_range(start_date, end_date)

    output = eventdb.get_count_for_range(start_date, end_date)

    return output


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


def output_tweets_to_ical(list_of_tweets):

    ical_string = ("BEGIN:VCALENDAR\nVERSION:2.0\n"
                   "PRODID:-//Louis Mitas//social-event-store 1.0.0//EN\n")

    time_now = str(datetime.datetime.now().time()).replace(":", "")[:6]
    date_now = str(datetime.datetime.now().date()).replace("-", "")

    for tweet in list_of_tweets:

        # Ever wonder how to get a datetime object out of a date and a timedelta? Wonder no more!
        start_time = datetime.datetime.combine(tweet[0], datetime.time()) + tweet[1]

        end_time = start_time + datetime.timedelta(0, 900)

        geocoordinates = "GEO:{};{}\n".format(tweet[5], tweet[6]) if tweet[5] else str()

        ical_string += word_wrap("BEGIN:VEVENT\n"
                                 "UID:{}{}@social-event-store\n"
                                 "DTSTAMP:{}T{}Z\n"
                                 "DTSTART:{}T{}Z\n"
                                 "DTEND:{}T{}Z\n"
                                 "{}"
                                 "SUMMARY:{}\n"
                                 "DESCRIPTION:{}\\n\\nhttps://twitter.com/i/status/{} | via {}\n"
                                 "END:VEVENT\n".format(tweet[2],
                                                       time_now,
                                                       date_now,
                                                       time_now,
                                                       str(tweet[0]).replace("-", ""),
                                                       str(start_time.time()).replace(":", ""),
                                                       str(end_time.date()).replace("-", ""),
                                                       str(end_time.time()).replace(":", ""),
                                                       geocoordinates,
                                                       tweet[3].replace("\n", " ").replace("\r", " "),
                                                       tweet[3].replace("\n", "\\n").replace("\r", "\\n"),
                                                       tweet[2],
                                                       tweet[4]
                                                       ))

    ical_string += "END:VCALENDAR"

    return ical_string


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


def tweets_in_local_time(tweets, user_prefs, am_pm_time=False):

    output_tweets = list()

    for tweet in tweets:
        tweet_dtime = datetime.datetime.combine(tweet[0], datetime.time()) + tweet[1]
        tweet_dtime = utc_to_local(tweet_dtime, timezone=user_prefs.timezone)

        tweet_out = list()
        tweet_out.append(tweet_dtime.date())
        time = tweet_dtime.strftime('%I:%M:%S %p') if am_pm_time else tweet_dtime.time()
        tweet_out.append(time)

        for i in range(2, len(tweet)):
            tweet_out.append(tweet[i])

        output_tweets.append(tweet_out)

    return output_tweets


def search_for_term(search_term):

    output = eventdb.get_search_term(search_term)

    return output


def calendar_grid(date_in_month, **kwargs):
    # Find the first day of the month
    first_of_month = datetime.date(date_in_month.year, date_in_month.month, 1)
    month_grid = list()

    # If we pass in the tweets object, we can use that instead of DB calls
    tweets = kwargs.get("tweets") or []

    # Track what month we're on and where we started
    cal_month = first_of_month
    curr_month = cal_month.month

    # Calender is a list of lists of dicts that contain all the info we need
    # Items in every dict are "day", "count", "full_date", and "color"
    # It is actually arranged like a calendar (each row is a week) to aid rendering the template
    start_time = datetime.datetime.now()
    while len(month_grid) < 6:
        week_list = list()
        while len(week_list) < 7:
            curr_day = dict()
            curr_day["day"] = str(cal_month.day) if cal_month.month == curr_month \
                and cal_month.weekday() == len(week_list) \
                else str()
            # either get from DB or use existing count from tweets
            curr_day["count"] = (tweets[cal_month.day - 1]["count"] if tweets else
                                 get_count_for_date_range(str(cal_month), str(cal_month))[0][0]) if \
                curr_day["day"] else -1
            curr_day["full_date"] = cal_month.strftime('%Y-%m-%d') if curr_day["day"] else str()
            week_list.append(curr_day)
            cal_month = cal_month + datetime.timedelta(1, 0) if curr_day["day"] else cal_month
        month_grid.append(week_list)

    # Performance log message
    print("Calculated {}-{} in {}".format(date_in_month.year,
                                          str(date_in_month.month),
                                          datetime.datetime.now() - start_time))

    # Monthly max will determine the high end of the color gradient
    # TODO: Move this inside the calendar setup logic for efficiency's sake
    monthly_max = 0
    for week in month_grid:
        for day in week:
            monthly_max = day["count"] if day["count"] > monthly_max else monthly_max

    # Creating colors on a gradient based on count. Technically this should be able to handle
    # a range of infinite size in any given month, but the colors will start to be absolutely
    # indistinguishable above 510 tweets. The practical number will be much lower.
    heat_map_colors = dict()
    for i in range(1, monthly_max + 1):
        pos = 510 / (monthly_max + 1) * i
        plus_red = int(pos) if pos < 256 else 255
        minus_green = int(pos - 255) if pos > 255 else 0

        hex_color = "#{}{}00".format(to_hex(plus_red),
                                     to_hex(255-minus_green))

        heat_map_colors[i] = hex_color

    # Because we made a dict that already has a color assigned for each possible count,
    # it's beyond easy to slot the appropriate color into each calendar day.
    for week in month_grid:
        for day in week:
            day["color"] = heat_map_colors[day["count"]] if day["count"] > 0 else "#555555"

    return month_grid


# Surely there are better implementations of dec-to-hex converters out there, but by god I
# won't use them. This is a quick and dirty two-digit converter which is all I need. I'm
# not proud of it, but it gets the job done. I'm going to call it "purpose-built" because it
# sounds fancier that way.
def to_hex(integer):
    above_dec = {10: 'a',
                 11: 'b',
                 12: 'c',
                 13: 'd',
                 14: 'e',
                 15: 'f'}

    first_digit = int(integer / 16)
    first_digit = above_dec[first_digit] if first_digit > 9 else first_digit

    second_digit = integer % 16
    second_digit = above_dec[second_digit] if second_digit > 9 else second_digit

    return "{}{}".format(first_digit, second_digit)


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

    tweets = tweets_in_local_time(get_tweets_for_date_range(first_day, last_day, user_prefs),
                                  user_prefs, True)
    tweets_by_date = dict()
    for tweet in tweets:
        if not tweets_by_date.get(tweet[0].strftime("%Y-%m-%d")):
            tweets_by_date[tweet[0].strftime("%Y-%m-%d")] = []
        tweets_by_date[tweet[0].strftime("%Y-%m-%d")].append(tweet)

    for day in list_of_days:
        day["events"] = tweets_by_date.get(day["date_full"]) or day["events"]
        day["count"] = len(day["events"])

    print(f"Got month of tweets parsed in {datetime.datetime.now() - start_time}")

    return list_of_days


def reverse_events(day_list):
    day_list.reverse()
    for day in day_list:
        day["events"].reverse()

    return day_list



def build_date_pickers():

    years = eventdb.get_years_with_data()

    months = list()

    for i in range(1, 13):
        month_detail = dict()
        month_detail["name"] = datetime.date(1, i, 1).strftime("%B")
        month_detail["value"] = i
        months.append(month_detail)

    date_picker = dict()

    date_picker["years"] = years
    date_picker["months"] = months

    return date_picker


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

                if ("data/js/tweets" in entry and ".js" in entry) or ("tweet.js" in entry):
                    js_file_to_save = zipfile_to_process.read(entry)
                    output_file = open(f"{output_path}/{entry.split('/')[-1]}", "wb")
                    output_file.write(js_file_to_save)
                    output_file.close()

                elif "account.js" in entry:
                    account_js = zipfile_to_process.read(entry)
                    Path.mkdir(Path(f"{output_path}/acct"))
                    output_acct = open(f"{output_path}/acct/account.js", "wb")
                    output_acct.write(account_js)
                    output_acct.close()

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


def fix_symbols(message):

    symbols = {"&gt;": ">",
               "&lt;": "<",
               "&quot;": "\"",
               "&#039;": "'",
               "&amp;": "&"}

    for symbol in symbols:
        message = message.replace(symbol, symbols[symbol])

    return message


def database_running():

    try:
        cnx = eventdb.create_connection('social')
        eventdb.close_connection(cnx)

        return True

    except:
        return False


def export_ical(tweets):
    ical_text = output_tweets_to_ical(tweets)
    output_path = f"output/export_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.ics"

    with open(output_path, "w", encoding="utf8") as ics_file:
        ics_file.write(ical_text)

    return output_path


class UserPreferences:
    def __init__(self, user_id):
        self.user_id = user_id
        db_prefs = eventdb.get_user_preferences(self.user_id)
        self.timezone = db_prefs.get('timezone') or 'UTC'
        self.reverse_order = db_prefs.get('reverse_order')
        print(self.reverse_order)

    def update(self, **kwargs):
        self.timezone = kwargs.get('timezone') or self.timezone
        self.reverse_order = kwargs.get('reverse_order')
        eventdb.set_user_preferences(1,
                                     timezone=self.timezone,
                                     reverse_order=self.reverse_order)


if __name__ == '__main__':

    # # Inside acct directory place account.js if you have it
    # account_id = get_account_id('acct/account.js')
    #
    # # If you have multiple directories you can make a list of all of them and
    # # then iterate through them.
    # directory_list = ['data/2013', 'data/2014', 'data/2014.1', 'data/2015',
    #                   'data/2016', 'data/2017', 'data/2018', 'data/2019']
    #
    # for directory in directory_list:
    #     start_time = datetime.datetime.now()
    #     print("processing {}".format(directory))
    #     process_directory(directory, account_id)
    #     print("Finished in {}".format(datetime.datetime.now() - start_time))

    # # Set date range of tweets that you want for iCal file
    # tweet_subset = get_tweets_for_date_range('2017-01-01', '2019-12-31')
    # ical_data = output_tweets_to_ical(tweet_subset)
    #
    # # Create a file in the output directory for the iCal data
    # with open("output/tweets-2017-19.ics", "w", encoding="utf8") as ics_file:
    #     ics_file.write(ical_data)

    # grid = calendar_grid(datetime.date(2010, 11, 6))
    #
    # for row in grid:
    #     print(row)

    # one_month = get_one_month_of_events(2008, 11)
    # print(one_month)

    # print(build_date_pickers())

    # temporary_path = unpack_and_store_files("data/17079629_ee3bcdc890285fc6c215527dca530f05fdd937ae.zip", "output")
    # print(temporary_path)

    # cleanup('output/20200610223504349588')

    exit(0)
