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

def parseRawTwitter(rawFileText):
    openBracketPos = -1
    closeBracketPos = -1
    listOfTweets = []
    
    while(rawFileText.find("{", closeBracketPos + 1) > -1):
        
        openBracketPos = rawFileText.find("{", closeBracketPos + 1)
        maybeClosePos = rawFileText.find("}\n}, {", openBracketPos + 1)
        
        if(maybeClosePos == -1): closeBracketPos = rawFileText.find("}\n} ]", openBracketPos + 1) + 3
        else: closeBracketPos = rawFileText.find("}\n}, {", openBracketPos + 1) + 3
        
        singleTweetString = rawFileText[openBracketPos:closeBracketPos]
        #print("STARTING A NEW TWEET\n" + singleTweetString)
        
        tweetJson = json.loads(singleTweetString)
        
        rawTweetText = str(tweetJson["text"])
        convertedTweetText = bytes(rawTweetText,"latin1",errors="ignore").decode("latin1")
        tweetJson["text"] = convertedTweetText
#         print(convertedTweetText)
        
        
        tweetTimeStamp = parseDateTime(tweetJson["created_at"])
        tweetJson["sqlDate"] = str(tweetTimeStamp.date())
        tweetJson["sqlTime"] = str(tweetTimeStamp.time())
        
        listOfTweets.append(tweetJson)
    return listOfTweets

def parseDateTime (rawStamp):
    if(rawStamp[0:4].isnumeric() == True):
        
        yr = int(rawStamp[0:4])
        mo = int(rawStamp[5:7])
        dy = int(rawStamp[8:10])
        hr = int(rawStamp[11:13])
        mn = int(rawStamp[14:16])
        sc = int(rawStamp[17:19])
        
    elif(rawStamp[0:3].isalpha() == True):
        yr = int(rawStamp[26:30])
        mo = numberMonth(rawStamp[4:7])
        dy = int(rawStamp[8:10])
        hr = int(rawStamp[11:13])
        mn = int(rawStamp[14:16])
        sc = int(rawStamp[17:19])
        
    elif(rawStamp.find(" - ") >= 0):
        yr = int(rawStamp[len(rawStamp)-4:len(rawStamp)])
        
    postDateTime = datetime.datetime(yr,mo,dy,hour = hr,minute = mn,second = sc)
    
    return postDateTime

def numberMonth(monthStr):
    monthStr = monthStr.capitalize()
    if(monthStr[0:3] == "Jan"): monthNum = 1
    elif(monthStr[0:3] == "Feb"): monthNum = 2
    elif(monthStr[0:3] == "Mar"): monthNum = 3
    elif(monthStr[0:3] == "Apr"): monthNum = 4
    elif(monthStr[0:3] == "May"): monthNum = 5
    elif(monthStr[0:3] == "Jun"): monthNum = 6
    elif(monthStr[0:3] == "Jul"): monthNum = 7
    elif(monthStr[0:3] == "Aug"): monthNum = 8
    elif(monthStr[0:3] == "Sep"): monthNum = 9
    elif(monthStr[0:3] == "Oct"): monthNum = 10
    elif(monthStr[0:3] == "Nov"): monthNum = 11
    elif(monthStr[0:3] == "Dec"): monthNum = 12
    
    return monthNum

def processDirectory(dirPath):
    
    targetDir = Path(dirPath)
    
    cnx = eventdb.createConnection()
    
    for targetFile in targetDir.iterdir():
        
        with open(targetFile,"r",encoding="latin1",errors="replace") as file:
            file = file.read()
            listOfTweets = parseRawTwitter(file)
            eventdb.insertTweets(listOfTweets,cnx)
            
    
    eventdb.closeConnection(cnx)
    
def getOneTweet(tweetid):
    
    cnx = eventdb.createConnection('test_one')
    cursor = cnx.cursor()
    
    theTweet = eventdb.getTweet(cursor,tweetid)
    
    output = []
    
    for i in cursor:
        output.append(i)
    
    eventdb.closeConnection(cnx)
    
    return output

# processDirectory("data")

print(getOneTweet('155316636524613633'))