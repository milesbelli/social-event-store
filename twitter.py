import urllib.request
import json
import datetime
import eventdb
from pathlib import Path


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
    
    the_tweet = eventdb.get_tweet(cursor, tweetid)
    
    output = list()
    
    for i in cursor:
        output.append(i)
    
    eventdb.close_connection(cnx)
    
    return output


def get_tweets_for_date_range(start_date, end_date):
    cnx = eventdb.create_connection("social")
    cursor = cnx.cursor()

    eventdb.get_date_range(cursor, start_date, end_date)
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
    #     start_time=datetime.datetime.now()
    #     print("processing {}".format(directory))
    #     process_directory(directory, account_id)
    #     print("Finished in {}".format(datetime.datetime.now() - start_time))

    # # Set date range of tweets that you want for iCal file
    # tweet_subset = get_tweets_for_date_range('2018-01-01', '2019-12-31')
    # ical_data = output_tweets_to_ical(tweet_subset)
    #
    # # Create a file in the output directory for the iCal data
    # with open("output/tweets-2018-19.ics", "w") as ics_file:
    #     ics_file.write(ical_data)

    exit(0)
