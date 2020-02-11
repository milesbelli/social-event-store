import mysql.connector
import secure


def create_connection(dbname):
    
    cnx = mysql.connector.connect(user=secure.username(),
                                  password=secure.password(),
                                  host='127.0.0.1')
    
    cursor = cnx.cursor()
    cursor.execute('CREATE DATABASE IF NOT EXISTS {}'.format(dbname))
    cnx.database = dbname
    
    return cnx


def insert_tweets(list_of_tweets, cnx):
    
    tweets_total = len(list_of_tweets)
    values_tweets = values_events = values_hashtags = ""
    
    # These next two values assume the list is ordered; if Twitter changes their archiving process, this could break
    last_tweet = list_of_tweets[0]["id"]
    first_tweet = list_of_tweets[tweets_total - 1]["id"]
    
    cursor = cnx.cursor()
    
    tweets_in_db = get_existing_tweets(cursor, first_tweet, last_tweet)
    
    for i in range(tweets_total):
        
        tweet_id = list_of_tweets[i]["id"]
        
        if tweet_id not in tweets_in_db:
            if i > 0:
                values_tweets += ","
                values_events += ","

            value_to_append = "('{}','{}','{}','{}',{},{},{},'{}',{})"

            values_tweets += "".join(value_to_append.format(tweet_id,
                                                            "1",                                       #This is hardcoded and will need to change
                                                            list_of_tweets[i]["text"].replace("'","''"), #Escape character for apostrophes
                                                            list_of_tweets[i]["user"]["id"],
                                                            list_of_tweets[i]["latitude"],
                                                            list_of_tweets[i]["longitude"],
                                                            list_of_tweets[i]["in_reply_to_status_id"],
                                                            list_of_tweets[i]["client_name"],
                                                            list_of_tweets[i]["rt_id"]))
            
            value_to_append = "('{}','{}','{}','{}')"
            
            values_events += "".join(value_to_append.format("1",                                       #Replace hardcoding here too
                                                            list_of_tweets[i]["sqlDate"],
                                                            list_of_tweets[i]["sqlTime"],
                                                            tweet_id))
            
            value_to_append = "('{}','{}','{}')"
            
            for hashtag in list_of_tweets[i]["entities"]["hashtags"]:
                
                if len(values_hashtags) > 0:
                    values_hashtags += ","
            
                values_hashtags += "".join(value_to_append.format(tweet_id,
                                                                hashtag["indices"][0],
                                                                hashtag["text"]))

    if len(values_tweets) > 0:
    
        sql_insert_tweets = ("INSERT INTO tweetdetails"
                             "(tweetid, userid, tweettext, twitteruserid, latitude, longitude, replyid, client, retweetid)"
                             "VALUES {}".format(values_tweets))
        
        cursor.execute(sql_insert_tweets)
        
    if len(values_events) > 0:
    
        sql_insert_events = ("INSERT INTO events"
                             "(userid, eventdate, eventtime, tweetid)"
                             "VALUES {}".format(values_events))
        
        cursor.execute(sql_insert_events)
        
    if len(values_hashtags) > 0:
        
        sql_insert_hashtags = ("INSERT INTO tweethashtags"
                               "(tweetid, ixstart, hashtag)"
                               "VALUES {}".format(values_hashtags))
        
        cursor.execute(sql_insert_hashtags)
    
    cnx.commit()
    cursor.close()
    
    
def get_existing_tweets(cursor, start=None, end=None):
      
    sql_get_all_tweet_ids = "SELECT tweetid FROM tweetdetails"
    
    if start is not None and end is not None:
        sql_get_all_tweet_ids = sql_get_all_tweet_ids + " WHERE tweetid BETWEEN '{}' AND '{}'".format(start,end)

    cursor.execute(sql_get_all_tweet_ids)
    
    output = list()
    
    for i in cursor:
        output.append(i[0])
    
    return output


def get_tweet(cursor, tweet_id):
    
    sql_tweet = ("SELECT events.eventdate, events.eventtime, tweetdetails.tweettext "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON events.tweet_id = tweetdetails.tweetid "
                 "WHERE tweetdetails.tweetid = '{}';".format(tweet_id))
    
    cursor.execute(sql_tweet)
    
    return cursor


def close_connection(cnx):

    return cnx.close()
