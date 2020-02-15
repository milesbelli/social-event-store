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

        tweet_details["text"] = rt_text or tweet_details["text"]

    return list_of_tweets


def get_account_id(file_path):
    with open(file_path) as acct:

        acct = acct.read()
        acct_text = acct[acct.index('[ {'):]
        acct_json = json.loads(acct_text)

        return acct_json[0]['account']['accountId']


def parse_date_time (raw_stamp):
    
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
    
    if month_str[0:3] == "Jan":
        return 1
    
    elif month_str[0:3] == "Feb":
        return 2
    
    elif month_str[0:3] == "Mar":
        return 3
    
    elif month_str[0:3] == "Apr":
        return 4
    
    elif month_str[0:3] == "May":
        return 5
    
    elif month_str[0:3] == "Jun":
        return 6
    
    elif month_str[0:3] == "Jul":
        return 7
    
    elif month_str[0:3] == "Aug":
        return 8
    
    elif month_str[0:3] == "Sep":
        return 9
    
    elif month_str[0:3] == "Oct":
        return 10
    
    elif month_str[0:3] == "Nov":
        return 11
    
    elif month_str[0:3] == "Dec":
        return 12
    

def get_client_name(client_string):
    try:
        start_pos = client_string.index('>') + 1
        end_pos = client_string.index('<', start_pos)
    
        return client_string[start_pos:end_pos]
    
    except:
        return client_string
    

def process_directory(dir_path, acct=None):
    
    target_dir = Path(dir_path)
    
    cnx = eventdb.create_connection('social')
    
    for target_file in target_dir.iterdir():
        
        with open(target_file, "r", errors="replace") as file:
            
            file = file.read()
            list_of_tweets = parse_js_text(file, acct)
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


if __name__ == '__main__':
    account_id = get_account_id('acct/account.js')
    directory_list = ['data/2013', 'data/2014', 'data/2014.5', 'data/2015',
                      'data/2016', 'data/2017', 'data/2018', 'data/2019']

    for directory in directory_list:
        process_directory(directory, account_id)

    a_tweet = (get_one_tweet('155316636524613633'))

    for tweet in a_tweet:
        for column in tweet:
            print(column)

    # with open("data2/tweet.js", errors="replace") as file:
    #     file = file.read()
    #     list_of_tweets = parse_js_text(file)
    #
    #
    # print(list_of_tweets[0])