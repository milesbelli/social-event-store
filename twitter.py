import urllib.request
import json
import datetime
import eventdb
from pathlib import Path

def retrieveFromTwitter(postId):

    tweetUrl = "https://twitter.com/milesbelli/status/" + str(postId)
    tweetPage = urllib.request.urlopen(tweetUrl)
    data = tweetPage.read()
    text = data.decode("utf-8")
    offset = text.find("\"metadata\">")
    timeStamp = text[offset+22:offset+44]
    timeStamp = timeStamp[0:timeStamp.find("<")]

    #This time is always going to be San Francisco time
    return timeStamp


def parse_js_text(text):

    tweets_text = text[text.index('[ {'):]
    list_of_tweets = json.loads(tweets_text)

    for tweet_details in list_of_tweets:

        tweet_timestamp = parseDateTime(tweet_details["created_at"])
        tweet_details["sqlDate"] = str(tweet_timestamp.date())
        tweet_details["sqlTime"] = str(tweet_timestamp.time())

        tweet_details["client_name"] = getClientName(tweet_details["source"])

        tweet_details["text"] = tweet_details.get("text") or tweet_details.get("full_text")

        # TODO: Handle new format that doesn't keep user info inside archive (account.js has info)
        tweet_details["user"] = tweet_details.get("user") or {"id": 0}

    return list_of_tweets


def parseDateTime (rawStamp):
    
    if rawStamp[0:4].isnumeric():
        
        yr = int(rawStamp[0:4])
        mo = int(rawStamp[5:7])
        dy = int(rawStamp[8:10])
        hr = int(rawStamp[11:13])
        mn = int(rawStamp[14:16])
        sc = int(rawStamp[17:19])
        
    elif rawStamp[0:3].isalpha():
        
        yr = int(rawStamp[26:30])
        mo = numberMonth(rawStamp[4:7])
        dy = int(rawStamp[8:10])
        hr = int(rawStamp[11:13])
        mn = int(rawStamp[14:16])
        sc = int(rawStamp[17:19])
        
    elif rawStamp.find(" - ") >= 0:
        
        yr = int(rawStamp[len(rawStamp)-4:len(rawStamp)])
        
    return datetime.datetime(yr,mo,dy,hour = hr,minute = mn,second = sc)
    

def numberMonth(monthStr):
    
    monthStr = monthStr.capitalize()
    
    if(monthStr[0:3] == "Jan"):
    
        return 1
    
    elif(monthStr[0:3] == "Feb"):
        
        return 2
    
    elif(monthStr[0:3] == "Mar"):
        
        return 3
    
    elif(monthStr[0:3] == "Apr"):
        
        return 4
    
    elif(monthStr[0:3] == "May"):
        
        return 5
    
    elif(monthStr[0:3] == "Jun"):
        
        return 6
    
    elif(monthStr[0:3] == "Jul"):
        
        return 7
    
    elif(monthStr[0:3] == "Aug"):
        
        return 8
    
    elif(monthStr[0:3] == "Sep"):
        
        return 9
    
    elif(monthStr[0:3] == "Oct"):
        
        return 10
    
    elif(monthStr[0:3] == "Nov"):
        
        return 11
    
    elif(monthStr[0:3] == "Dec"):
        
        return 12
    

def getClientName(client_string):
    try:
        start_pos = client_string.index('>') + 1
        end_pos = client_string.index('<',start_pos)
    
        return client_string[start_pos:end_pos]
    
    except:
        return client_string
    

def processDirectory(dirPath):
    
    targetDir = Path(dirPath)
    
    cnx = eventdb.create_connection('social')
    
    for targetFile in targetDir.iterdir():
        
        with open(targetFile, "r", errors="replace") as file:
            
            file = file.read()
            listOfTweets = parse_js_text(file)
            eventdb.insert_tweets(listOfTweets,cnx)

    
    eventdb.closeConnection(cnx)
    
def getOneTweet(tweetid):
    
    cnx = eventdb.create_connection('social')
    cursor = cnx.cursor()
    
    theTweet = eventdb.getTweet(cursor,tweetid)
    
    output = list()
    
    for i in cursor:
        output.append(i)
    
    eventdb.closeConnection(cnx)
    
    return output

if __name__ == '__main__':
    processDirectory("data2")

    #print(getOneTweet('155316636524613633'))

    # with open("data2/tweet.js", errors="replace") as file:
    #     file = file.read()
    #     list_of_tweets = parse_js_text(file)
    #
    #
    # print(list_of_tweets[0])