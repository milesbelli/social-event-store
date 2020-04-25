import urllib.request
import json
import datetime
import eventdb
from pathlib import Path
import pytz


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

    # Format for database
    for tweet_details in list_of_tweets:

        tweet_timestamp = parse_date_time(tweet_details["created_at"])

        tweet_details["sql_date"] = str(tweet_timestamp.date())
        tweet_details["sql_time"] = str(tweet_timestamp.time())

        tweet_details["client_name"] = get_client_name(tweet_details["source"])

        tweet_details["text"] = tweet_details.get("text") or tweet_details.get("full_text")

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
    
    for target_file in target_dir.iterdir():
        
        with open(target_file, "r", errors="replace") as file:
            
            file = file.read()
            list_of_tweets += parse_js_text(file, acct)

    eventdb.insert_tweets(list_of_tweets, cnx)

    eventdb.close_connection(cnx)

    
def get_one_tweet(tweetid):
    
    cnx = eventdb.create_connection('social')
    cursor = cnx.cursor()
    
    eventdb.get_tweet(cursor, tweetid)
    
    output = list()
    
    for i in cursor:
        output.append(i)
    
    eventdb.close_connection(cnx)
    
    return output


def localize_date_range(start_date, end_date):
    # First convert the str dates to datetime dates
    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")

    # Then add times to be datetime objects
    start_date = datetime.datetime.combine(start_date, datetime.time(0, 0))
    end_date = datetime.datetime.combine(end_date, datetime.time(23, 59, 59))

    # Then go from Local to UTC
    start_date = local_to_utc(start_date)
    end_date = local_to_utc(end_date)

    # Finally back to strings
    start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')

    return start_date, end_date


def get_tweets_for_date_range(start_date, end_date):
    cnx = eventdb.create_connection("social")
    cursor = cnx.cursor()

    start_date, end_date = localize_date_range(start_date, end_date)

    eventdb.get_datetime_range(cursor, start_date, end_date)
    output = list()

    for i in cursor:
        output.append(i)

    eventdb.close_connection(cnx)

    return output


def get_count_for_date_range(start_date, end_date):
    cnx = eventdb.create_connection("social")
    cursor = cnx.cursor()

    start_date, end_date = localize_date_range(start_date, end_date)

    eventdb.get_count_for_range(cursor, start_date, end_date)
    output = list()

    for i in cursor:
        output.append(i)

    eventdb.close_connection(cnx)

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

def utc_to_local(source_dt):
    # Use pytz module to convert a utc datetime to local datetime

    utc = pytz.timezone("utc")
    local = pytz.timezone("us/eastern")

    utc_dt = utc.localize(source_dt)
    return utc_dt.astimezone(local)


def local_to_utc(source_dt):
    # Use pytz module to convert a local datetime to utc datetime

    local = pytz.timezone("us/eastern")
    utc = pytz.timezone("utc")

    local_dt = local.localize(source_dt)
    return local_dt.astimezone(utc)


def tweets_in_local_time(tweets, am_pm_time=False):

    output_tweets = list()

    for tweet in tweets:
        tweet_dtime = datetime.datetime.combine(tweet[0], datetime.time()) + tweet[1]
        tweet_dtime = utc_to_local(tweet_dtime)

        tweet_out = list()
        tweet_out.append(tweet_dtime.date())
        time = tweet_dtime.strftime('%I:%M:%S %p') if am_pm_time else tweet_dtime.time()
        tweet_out.append(time)

        for i in range(2, len(tweet)):
            tweet_out.append(tweet[i])

        output_tweets.append(tweet_out)

    return output_tweets


def search_for_term(search_term):
    cnx = eventdb.create_connection("social")
    cursor = cnx.cursor()

    eventdb.get_search_term(cursor, search_term)
    output = list()

    for i in cursor:
        output.append(i)

    eventdb.close_connection(cnx)

    return output


def calendar_grid(date_in_month):
    first_of_month = datetime.date(date_in_month.year, date_in_month.month, 1)
    month_grid = list()
    i = 0
    j = first_of_month.weekday()

    cal_month = first_of_month
    curr_month = cal_month.month

    start_time = datetime.datetime.now()
    while len(month_grid) < 6:
        week_list = list()
        while len(week_list) < 7:
            curr_day = dict()
            curr_day["day"] = str(cal_month.day) if cal_month.month == curr_month \
                and cal_month.weekday() == len(week_list) \
                else str()
            curr_day["count"] = get_count_for_date_range(str(cal_month), str(cal_month))[0][0] if \
                curr_day["day"] else -1
            curr_day["full_date"] = cal_month.strftime('%Y-%m-%d')
            week_list.append(curr_day)
            cal_month = cal_month + datetime.timedelta(1, 0) if curr_day["day"] else cal_month
        month_grid.append(week_list)

    print("Calculated {}-{} in {}".format(cal_month.year,
                                          str(cal_month.month),
                                          datetime.datetime.now() - start_time))
    monthly_max = 0
    # monthly_min = month_grid[0][0]["count"]


    for week in month_grid:
        for day in week:
            monthly_max = day["count"] if day["count"] > monthly_max else monthly_max
            # monthly_min = day["count"] if -1 < day["count"] < monthly_min else monthly_min
    # print(monthly_min)
    # print(monthly_max)

    heat_map_colors = dict()

    for i in range(1, monthly_max + 1):
        pos = 510 / (monthly_max + 1) * i
        plus_red = int(pos) if pos < 256 else 255
        minus_green = int(pos - 255) if pos > 255 else 0

        hex_color = "#{}{}00".format(to_hex(plus_red),
                                     to_hex(255-minus_green))

        heat_map_colors[i] = hex_color

    # print(heat_map_colors)

    for week in month_grid:
        for day in week:
            day["color"] = heat_map_colors[day["count"]] if day["count"] > 0 else "#ffffff"

    return month_grid


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


if __name__ == '__main__':

    # Inside acct directory place account.js if you have it
    account_id = get_account_id('acct/account.js')

    # If you have multiple directories you can make a list of all of them and
    # then iterate through them.
    directory_list = ['data/2013', 'data/2014', 'data/2014.1', 'data/2015',
                      'data/2016', 'data/2017', 'data/2018', 'data/2019']

    for directory in directory_list:
        start_time = datetime.datetime.now()
        print("processing {}".format(directory))
        process_directory(directory, account_id)
        print("Finished in {}".format(datetime.datetime.now() - start_time))

    # # Set date range of tweets that you want for iCal file
    # tweet_subset = get_tweets_for_date_range('2018-01-01', '2019-12-31')
    # ical_data = output_tweets_to_ical(tweet_subset)
    #
    # # Create a file in the output directory for the iCal data
    # with open("output/tweets-2018-19.ics", "w", encoding="utf8") as ics_file:
    #     ics_file.write(ical_data)

    # grid = calendar_grid(datetime.date(2010, 11, 6))
    #
    # for row in grid:
    #     print(row)

    exit(0)
