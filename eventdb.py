import mysql.connector

def createConnection():
    
    cnx = mysql.connector.connect(user='lmitas',
                                  password='maggies2cute',
                                  host='127.0.0.1',
                                  database='test_one')
    
    return cnx


def insertTweets(listOfTweets,cnx):
    
    tweetsTotal = len(listOfTweets)
    valuesTweets = valuesEvents = ""
    
    # These next two values assume the list is ordered; if Twitter changes their archiving process, this could break
    lastTweet = listOfTweets[0]["id"]
    firstTweet = listOfTweets[tweetsTotal - 1]["id"]
    
    cursor = cnx.cursor()
    
    tweetsInDb = getExistingTweets(cursor,firstTweet,lastTweet)
    
    for i in range(tweetsTotal):
        
        tweetId = listOfTweets[i]["id"]
        
        if tweetId not in tweetsInDb:
            if i > 0:
                valuesTweets += ","
                valuesEvents += ","
                
            
            valueToAppend = "('{}','{}','{}','{}')"
            
            valuesTweets += "".join(valueToAppend.format(tweetId,
                                                         "1",                                       #This is hardcoded and will need to change
                                                         listOfTweets[i]["text"].replace("'","''"), #Escape character for apostrophes
                                                         listOfTweets[i]["user"]["id"]))
            
            
            valuesEvents += "".join(valueToAppend.format("1",                                       #Replace hardcoding here too
                                                         listOfTweets[i]["sqlDate"],
                                                         listOfTweets[i]["sqlTime"],
                                                         tweetId))

    if len(valuesTweets) > 0:
    
        sqlInsertTweets = ("INSERT INTO tweetdetails"
                           "(tweetid, userid, tweettext, twitteruserid)"
                           "VALUES {}".format(valuesTweets))
        
        cursor.execute(sqlInsertTweets)
        
    if len(valuesEvents) > 0:
    
        sqlInsertEvents = ("INSERT INTO events"
                           "(userid, eventdate, eventtime, tweetid)"
                           "VALUES {}".format(valuesEvents))
        
        cursor.execute(sqlInsertEvents)
    
    cnx.commit()
    cursor.close()
    
    
def getExistingTweets(cursor,start = None,end = None):
      
    sqlGetAllTweetIds = "SELECT tweetid FROM tweetdetails"
    
    if start is not None and end is not None:
        sqlGetAllTweetIds = sqlGetAllTweetIds + " WHERE tweetid BETWEEN '{}' AND '{}'".format(start,end)
            
            
    cursor.execute(sqlGetAllTweetIds)
    
    output = []
    
    for i in cursor:
        output.append(i[0])
    
    return output

def getTweet(cursor,tweetid):
    
    sqlTweet = ("SELECT events.eventdate, events.eventtime, tweetdetails.tweettext "
                "FROM tweetdetails "
                "LEFT JOIN events "
                "ON events.tweetid = tweetdetails.tweetid "
                "WHERE tweetdetails.tweetid = '{}';".format(tweetid))
    print(sqlTweet)
    
    cursor.execute(sqlTweet)
    
    return cursor

def closeConnection(cnx):

    return cnx.close()