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


def insert_tweets(listOfTweets,cnx):
    
    tweetsTotal = len(listOfTweets)
    valuesTweets = valuesEvents = values_hashtags = ""
    
    # These next two values assume the list is ordered; if Twitter changes their archiving process, this could break
    lastTweet = listOfTweets[0]["id"]
    firstTweet = listOfTweets[tweetsTotal - 1]["id"]
    
    cursor = cnx.cursor()
    
    tweetsInDb = get_existing_tweets(cursor,firstTweet,lastTweet)
    
    for i in range(tweetsTotal):
        
        tweetId = listOfTweets[i]["id"]
        
        if tweetId not in tweetsInDb:
            if i > 0:
                valuesTweets += ","
                valuesEvents += ","

            valueToAppend = "('{}','{}','{}','{}',{},{},{},'{}',{})"

            valuesTweets += "".join(valueToAppend.format(tweetId,
                                                         "1",                                       #This is hardcoded and will need to change
                                                         listOfTweets[i]["text"].replace("'","''"), #Escape character for apostrophes
                                                         listOfTweets[i]["user"]["id"],
                                                         listOfTweets[i]["latitude"],
                                                         listOfTweets[i]["longitude"],
                                                         listOfTweets[i]["in_reply_to_status_id"],
                                                         listOfTweets[i]["client_name"],
                                                         listOfTweets[i]["rt_id"]))
            
            valueToAppend = "('{}','{}','{}','{}')"
            
            valuesEvents += "".join(valueToAppend.format("1",                                       #Replace hardcoding here too
                                                         listOfTweets[i]["sqlDate"],
                                                         listOfTweets[i]["sqlTime"],
                                                         tweetId))
            
            valueToAppend = "('{}','{}','{}')"
            
            for hashtag in listOfTweets[i]["entities"]["hashtags"]:
                
                if len(values_hashtags) > 0:
                    values_hashtags += ","
            
                values_hashtags += "".join(valueToAppend.format(tweetId,
                                                                hashtag["indices"][0],
                                                                hashtag["text"]))

    if len(valuesTweets) > 0:
    
        sqlInsertTweets = ("INSERT INTO tweetdetails"
                           "(tweetid, userid, tweettext, twitteruserid, latitude, longitude, replyid, client, retweetid)"
                           "VALUES {}".format(valuesTweets))
        
        cursor.execute(sqlInsertTweets)
        
    if len(valuesEvents) > 0:
    
        sqlInsertEvents = ("INSERT INTO events"
                           "(userid, eventdate, eventtime, tweetid)"
                           "VALUES {}".format(valuesEvents))
        
        cursor.execute(sqlInsertEvents)
        
    if len(values_hashtags) > 0:
        
        sql_insert_hashtags = ("INSERT INTO tweethashtags"
                               "(tweetid, ixstart, hashtag)"
                               "VALUES {}".format(values_hashtags))
        
        cursor.execute(sql_insert_hashtags)
    
    cnx.commit()
    cursor.close()
    
    
def get_existing_tweets(cursor, start=None, end=None):
      
    sqlGetAllTweetIds = "SELECT tweetid FROM tweetdetails"
    
    if start is not None and end is not None:
        sqlGetAllTweetIds = sqlGetAllTweetIds + " WHERE tweetid BETWEEN '{}' AND '{}'".format(start,end)
            
            
    cursor.execute(sqlGetAllTweetIds)
    
    output = list()
    
    for i in cursor:
        output.append(i[0])
    
    return output

def getTweet(cursor,tweetid):
    
    sqlTweet = ("SELECT events.eventdate, events.eventtime, tweetdetails.tweettext "
                "FROM tweetdetails "
                "LEFT JOIN events "
                "ON events.tweetid = tweetdetails.tweetid "
                "WHERE tweetdetails.tweetid = '{}';".format(tweetid))
    
    cursor.execute(sqlTweet)
    
    return cursor

def closeConnection(cnx):

    return cnx.close()