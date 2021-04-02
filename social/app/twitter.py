import urllib.request
import json
import datetime
import common, eventdb
from pathlib import Path
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

    common.cleanup(dir_path)


def process_from_file(file_path):

    process_dir = common.unpack_and_store_files(file_path, "output")
    process_directory(process_dir)


def get_count_for_date_range(start_date, end_date):

    start_date, end_date = common.localize_date_range(start_date, end_date)

    output = eventdb.get_count_for_range(start_date, end_date)

    return output


def search_for_term(search_term, user_prefs):

    filters = user_prefs.get_filters()

    output = eventdb.get_search_term(search_term, filters)

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
                                 get_count_for_date_range(str(cal_month), str(cal_month))[0]["count"]) if \
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


def reverse_events(day_list):
    day_list.reverse()
    for day in day_list:
        if type(day) == dict:
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

def get_status_from_twitter(status_id):

    reply_to = eventdb.get_in_reply_to(status_id)

    if not reply_to:
        request_string = (f"https://cdn.syndication.twimg.com/tweet?id={status_id}&lang=en")
        response = requests.get(request_string)
        if response.status_code == 200:
            output_status = json.loads(response.content)

            eventdb.insert_in_reply_to(output_status["id_str"],
                                       output_status["created_at"],
                                       output_status["user"]["screen_name"],
                                       output_status.get("in_reply_to_status_id_str"),
                                       output_status.get("in_reply_to_user_id_str"),
                                       output_status["text"],
                                       output_status["user"]["id_str"],
                                       output_status["lang"])

            output_status["text"] = (output_status["text"] +
                                     f" <a class='view_link' target='_blank' href='https://twitter.com/i/status/{status_id}'>View Online</a>")
            return output_status
        else:
            output_status = {"user": {"screen_name":""},
                             "text": f"<a style='font-size:14px' target='_blank' href='https://twitter.com/i/status/{status_id}'>View Online</a>"}
            return output_status
    else:
        reply_to["text"] = (reply_to["text"] +
                            f" <a class='view_link' target='_blank' href='https://twitter.com/i/status/{status_id}'>View Online</a>")
        return reply_to


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
