import json
import datetime
import eventdb
from pathlib import Path

def parseRawTwitter(rawFileText):
    
    openBracketPos = closeBracketPos = -1
    listOfTweets = list()
    
    while(rawFileText.find("{", closeBracketPos + 1) > -1):
        
        openBracketPos = rawFileText.find("{", closeBracketPos + 1)
        maybeClosePos = rawFileText.find("}\n}, {", openBracketPos + 1)
        
        searchString = "}\n} ]" if maybeClosePos == -1 else "}\n}, {"
        
        closeBracketPos = rawFileText.find(searchString, openBracketPos + 1) + 3
            
        singleTweetString = rawFileText[openBracketPos:closeBracketPos]
        
        tweetJson = json.loads(singleTweetString)
        
        rawTweetText = str(tweetJson["text"])
        convertedTweetText = bytes(rawTweetText,"latin1",errors="ignore").decode("latin1")
        tweetJson["text"] = convertedTweetText
        
        tweetTimeStamp = parseDateTime(tweetJson["created_at"])
        tweetJson["sqlDate"] = str(tweetTimeStamp.date())
        tweetJson["sqlTime"] = str(tweetTimeStamp.time())
        
        tweetJson['client_name'] = getClientName(tweetJson['source'])
        
        listOfTweets.append(tweetJson)
        
    return listOfTweets

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
    start_pos = client_string.find('>') + 1
    end_pos = client_string.find('<',start_pos)
    
    return client_string[start_pos:end_pos]
    

def processDirectory(dirPath):
    
    targetDir = Path(dirPath)
    
    cnx = eventdb.createConnection('social')
    
    for targetFile in targetDir.iterdir():
        
        with open(targetFile,"r",encoding="latin1",errors="replace") as file:
            
            file = file.read()
            listOfTweets = parseRawTwitter(file)
            eventdb.insertTweets(listOfTweets,cnx)
            
    
    eventdb.closeConnection(cnx)
    
def getOneTweet(tweetid):
    
    cnx = eventdb.createConnection('social')
    cursor = cnx.cursor()
    
    theTweet = eventdb.getTweet(cursor,tweetid)
    
    output = list()
    
    for i in cursor:
        output.append(i)
    
    eventdb.closeConnection(cnx)
    
    return output

if __name__ == '__main__':
    processDirectory("data")

    #print(getOneTweet('155316636524613633'))