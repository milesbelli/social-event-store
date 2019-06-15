import mysql.connector
import secure

def createConnection(dbname):
    
    cnx = mysql.connector.connect(user=secure.username(),
                                  password=secure.password(),
                                  host='127.0.0.1')
    
    cursor = cnx.cursor()
    cursor.execute('CREATE DATABASE IF NOT EXISTS {}'.format(dbname))
    cnx.database = dbname
    
    return cnx

def insertTweets(listOfTweets,cnx):
    
    tweetsTotal = len(listOfTweets)
    valuesTweets = valuesEvents = ""
    
    tweetmods = list()
    
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
            
            if "coordinates" in listOfTweets[i]["geo"]:
                tweetmods.append("UPDATE tweetdetails SET latitude = {}, longitude = {} WHERE tweetid = {};".format(listOfTweets[i]["geo"]["coordinates"][0],
                                                                                                          listOfTweets[i]["geo"]["coordinates"][1],
                                                                                                          tweetId))
            
            valueToAppend = "('{}','{}','{}','{}')"
            
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
        
    for entry in tweetmods:
        cursor.execute(entry)
    
    cnx.commit()
    cursor.close()
    
    
def getExistingTweets(cursor,start = None,end = None):
      
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