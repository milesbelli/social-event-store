import mysql.connector
import secure
import datetime
import common


def create_connection(dbname):
    
    cnx = mysql.connector.connect(user=secure.username(),
                                  password=secure.password(),
                                  host='127.0.0.1')
    cnx.set_charset_collation("utf8mb4", "utf8mb4_general_ci")
    
    cursor = cnx.cursor()
    cursor.execute('CREATE DATABASE IF NOT EXISTS {}'.format(dbname))
    cnx.database = dbname
    
    return cnx


def insert_tweets(list_of_tweets, cnx):
    
    tweets_total = len(list_of_tweets)
    values_tweets = values_events = values_hashtags = values_duplicates = ""
    
    cursor = cnx.cursor()
    
    tweets_in_db = get_existing_tweets(cursor)

    duplicate_dict = dict()

    for i in range(tweets_total):
        
        tweet_id = str(list_of_tweets[i]["id"])
        
        if tweet_id not in tweets_in_db:
            if len(values_tweets) > 0:
                values_tweets += ","
                values_events += ","

            value_to_append = "('{}','{}','{}','{}',{},{},{},'{}',{})"

            values_tweets += "".join(value_to_append.format(tweet_id,
                                                            "1",                                       # This is hardcoded and will need to change
                                                            list_of_tweets[i]["text"].replace("'", "''"),  # Escape character for apostrophes
                                                            list_of_tweets[i]["user"]["id"],
                                                            list_of_tweets[i]["latitude"],
                                                            list_of_tweets[i]["longitude"],
                                                            list_of_tweets[i]["in_reply_to_status_id"],
                                                            list_of_tweets[i]["client_name"],
                                                            list_of_tweets[i]["rt_id"]))
            
            value_to_append = "('{}','{}','{}','{}','{}')"
            
            values_events += "".join(value_to_append.format("1",                                       #Replace hardcoding here too
                                                            list_of_tweets[i]["sql_date"],
                                                            list_of_tweets[i]["sql_time"],
                                                            "twitter",
                                                            tweet_id))
            
            value_to_append = "('{}','{}','{}')"
            
            for hashtag in list_of_tweets[i]["entities"]["hashtags"]:
                
                if len(values_hashtags) > 0:
                    values_hashtags += ","
            
                values_hashtags += "".join(value_to_append.format(tweet_id,
                                                                hashtag["indices"][0],
                                                                hashtag["text"]))
        else:
            # Tweet is in db, so add to duplicate list for checking
            duplicate_dict[str(list_of_tweets[i]["id"])] = list_of_tweets[i]
            values_duplicates = tweet_id if len(values_duplicates) == 0 else values_duplicates + ", " + tweet_id


    if len(values_tweets) > 0:
    
        sql_insert_tweets = ("INSERT INTO tweetdetails"
                             "(tweetid, userid, tweettext, twitteruserid, latitude, longitude, replyid, client, retweetid)"
                             "VALUES {}".format(values_tweets))
        
        cursor.execute(sql_insert_tweets)
        
    if len(values_events) > 0:
    
        sql_insert_events = ("INSERT INTO events"
                             "(userid, eventdate, eventtime, eventtype, detailid)"
                             "VALUES {}".format(values_events))
        
        cursor.execute(sql_insert_events)
        
    if len(values_hashtags) > 0:
        
        sql_insert_hashtags = ("INSERT INTO tweethashtags"
                               "(tweetid, ixstart, hashtag)"
                               "VALUES {}".format(values_hashtags))
        
        cursor.execute(sql_insert_hashtags)

    if len(values_duplicates) > 0:

        sql_get_duplicate_data = ("SELECT events.detailid, eventdate, eventtime, client FROM events "
                                  "LEFT JOIN tweetdetails ON events.detailid = tweetdetails.tweetid "
                                  "WHERE events.detailid IN ({}) AND events.eventtype='twitter'".format(values_duplicates))

        cursor.execute(sql_get_duplicate_data)

        conflicting_duplicates_dict = dict()

        for i in cursor:
            conflicting_duplicates_dict[str(i[0])] = dict()

            if duplicate_dict[str(i[0])]["client_name"] != i[3]:
                conflicting_duplicates_dict[str(i[0])].update({"client_name":
                                                               duplicate_dict[str(i[0])]["client_name"]})
            if duplicate_dict[str(i[0])]["sql_date"] != str(i[1]):
                conflicting_duplicates_dict[str(i[0])].update({"eventdate":
                                                               duplicate_dict[str(i[0])]["sql_date"]})
            if duplicate_dict[str(i[0])]["sql_time"] != str((datetime.datetime(2000, 1, 1) + i[2]).time()):
                conflicting_duplicates_dict[str(i[0])].update({"eventtime":
                                                               duplicate_dict[str(i[0])]["sql_time"]})

        # Optimize this with Pandas, potentially
        sql_get_previous_duplicates = "SELECT * from tweetconflicts"

        cursor.execute(sql_get_previous_duplicates)

        unique_conflicts = str()

        # Prune all the duplicate duplicates out first
        for i in cursor:
            current_duplicate = conflicting_duplicates_dict.get(str(i[0])) or dict()
            if current_duplicate.get(i[1]) == i[2]:
                conflicting_duplicates_dict[str(i[0])].pop(i[1])

        # Now that we know all duplicates left are unique, add them to the string

        for duplicate_tweet in conflicting_duplicates_dict:
            for duplicate_item in conflicting_duplicates_dict[duplicate_tweet]:
                add_to_string = "('{}','{}','{}')".format(duplicate_tweet, duplicate_item,
                                                    conflicting_duplicates_dict[duplicate_tweet][duplicate_item])
                unique_conflicts = add_to_string if len(unique_conflicts) == 0 else unique_conflicts +\
                                                                                    ", " + add_to_string
        if len(unique_conflicts) > 0:

            sql_insert_conflicts = "INSERT INTO tweetconflicts VALUES {}".format(unique_conflicts)
            cursor.execute(sql_insert_conflicts)

    cnx.commit()
    cursor.close()


def insert_fitbit_sleep(sleep, user_prefs):
    cnx = create_connection('social')
    cursor = cnx.cursor()
    user_id = 1                                # Static for now
    values_list = str()

    # Establish list of existing sleep events to eliminate duplicates
    sql_get_all_logids = f"SELECT logid FROM fitbit_sleep WHERE userid = {user_id}"

    cursor.execute(sql_get_all_logids)

    sql_results = list()
    sleep_levels = dict()

    for i in cursor:
        sql_results.append(i[0])

    # Loop over sleep event list
    for session in sleep:
        log_id = session["logId"]

        # Add any previously unrecorded sleep to the list of values
        if log_id not in sql_results:

            # Extra comma separator in between multiple values
            if len(values_list) > 0:
                values_list += ", "

            start_date_time = session["startTime"]
            end_date_time = session["endTime"]
            timezone = user_prefs.timezone
            duration = session["duration"]
            main_sleep = 1 if session["mainSleep"] else 0

            values_list += (f"('{user_id}', '{log_id}', '{start_date_time}', '{end_date_time}',"
                            f" '{timezone}', '{duration}', '{main_sleep}')")

            sleep_levels[log_id] = session["levels"]

    if len(values_list) > 0:
        sql_add_to_db = ("INSERT INTO fitbit_sleep (userid, logid, startdatetime,"
                         " enddatetime, timezone, duration, mainsleep) "
                         f"VALUES {values_list}")

        cursor.execute(sql_add_to_db)

        # Need to find all events just added which are not yet in the events table, so they can be added.
        sql_get_newly_added_sleep = ("SELECT userid, startdatetime, sleepid, logid "
                                     "FROM fitbit_sleep WHERE sleepid NOT IN "
                                     "(SELECT detailid FROM events WHERE eventtype = 'fitbit-sleep')")

        cursor.execute(sql_get_newly_added_sleep)

        new_sleep_events = list()
        event_values = str()
        logid_index = dict()

        for i in cursor:
            logid_index[i[3]] = i[2]
            new_sleep_events.append(i)

        # Populate secondary tables

        for log_id in sleep_levels:
            for level in sleep_levels[log_id]["summary"]:

                count = sleep_levels[log_id]["summary"][level].get("count")
                minutes = sleep_levels[log_id]["summary"][level].get("minutes")
                avg_minutes = sleep_levels[log_id]["summary"][level].get("thirtyDayAvgMinutes") or 0

                stages_values = f"('{logid_index[log_id]}', '{level}', '{count}', '{minutes}', '{avg_minutes}')"

                sql_add_stages = ("INSERT INTO fitbit_sleep_stages (sleepid, sleepstage, stagecount,"
                                  " stageminutes, avgstageminutes)"
                                  f" VALUES {stages_values}")

                cursor.execute(sql_add_stages)

            for item in sleep_levels[log_id]["data"]:

                sleep_date_time = item["dateTime"]
                level = item["level"]
                seconds = item["seconds"]

                data_values = f"('{logid_index[log_id]}', '{sleep_date_time}', '{level}', '{seconds}')"

                sql_add_data = ("INSERT INTO fitbit_sleep_data (sleepid, sleepdatetime, sleepstage, seconds)"
                                f"VALUES {data_values}")

                cursor.execute(sql_add_data)

        # Every event from the fitbit sleep table needs to have its time adjusted to UTC before
        # going in the events table. Fitbit sleep is tracked in local time but all events in events table
        # must be consistently UTC.
        for event in new_sleep_events:

            if len(event_values) > 0:
                event_values += ", "

            user_id = event[0]
            event_date = common.local_to_utc(event[1], timezone=timezone).strftime("%Y-%m-%d")
            event_time = common.local_to_utc(event[1], timezone=timezone).strftime("%H:%M:%S")
            event_id = event[2]

            event_values += f"('{user_id}', '{event_date}', '{event_time}', 'fitbit-sleep', '{event_id}')"

        sql_add_new_to_events_utc = ("INSERT INTO events (userid, eventdate, eventtime, eventtype, detailid) "
                                     f"VALUES {event_values};")

        cursor.execute(sql_add_new_to_events_utc)

        cnx.commit()
    cursor.close()

    
def get_existing_tweets(cursor):
      
    sql_get_all_tweet_ids = "SELECT tweetid FROM tweetdetails;"

    cursor.execute(sql_get_all_tweet_ids)
    
    output = list()
    
    for i in cursor:
        output.append(str(i[0]))
    
    return output


def get_tweet(tweet_id):

    cnx = create_connection('social')
    cursor = cnx.cursor()

    sql_tweet = ("SELECT eventdate, eventtime, tweetdetails.* "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 "WHERE tweetid = '{}' AND events.eventtype='twitter';".format(tweet_id))
    
    cursor.execute(sql_tweet)

    output = list()

    for i in cursor:
        output.append(i)

    close_connection(cnx)

    return output


def get_date_range(cursor, start_date, end_date):

    sql_query = ("SELECT eventdate, eventtime, detailid, tweettext, client, latitude, longitude "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 "WHERE eventdate >= '{}' AND eventdate <='{}'"
                 " AND events.eventtype='twitter';".format(start_date, end_date))

    cursor.execute(sql_query)

    return cursor


def get_datetime_range(start_datetime, end_datetime):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = ("SELECT eventdate, eventtime, detailid, tweettext, client, latitude, longitude "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 "WHERE CONCAT(eventdate,' ',eventtime) >= '{}' "
                 "AND CONCAT(eventdate,' ',eventtime) <= '{}' "
                 "ORDER BY eventdate ASC, eventtime ASC;".format(start_datetime, end_datetime))

    query_start_time = datetime.datetime.now()
    cursor.execute(sql_query)

    print(f'Returned query:\n{sql_query}\n in {datetime.datetime.now() - query_start_time}')

    output = list()

    for i in cursor:
        output.append(i)

    close_connection(cnx)

    return output


def get_count_for_range(start_datetime, end_datetime):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = ("SELECT COUNT(*) "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 "WHERE CONCAT(eventdate,' ',eventtime) >= '{}' "
                 "AND CONCAT(eventdate,' ',eventtime) <= '{}';".format(start_datetime, end_datetime))

    cursor.execute(sql_query)

    output = list()

    for i in cursor:
        output.append(i)

    close_connection(cnx)

    return output


def get_search_term(search_term):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    search_term = search_term.replace("'", "''")
    search_term = search_term.replace("\\", "\\\\")
    search_term = search_term.replace("%", "\\%")
    search_term = search_term.replace("_", "\\_")

    sql_query = ("SELECT eventdate, eventtime, detailid, tweettext, client, latitude, longitude "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 f"WHERE tweettext LIKE '%{search_term}%' "
                 "ORDER BY eventdate ASC, eventtime ASC;")

    cursor.execute(sql_query)

    output = list()

    for i in cursor:
        output.append(i)

    close_connection(cnx)

    return output


def get_years_with_data():

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = "SELECT left(eventdate,4) FROM events GROUP BY left(eventdate,4) ORDER BY left(eventdate,4);"
    cursor.execute(sql_query)

    years = list()

    for i in cursor:
        years.append(i[0])

    close_connection(cnx)

    return years


def get_user_preferences(user_id):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = f"SELECT preference_key, preference_value FROM user_preference WHERE userid = {user_id};"
    cursor.execute(sql_query)

    print(sql_query)

    preferences = dict()

    for i in cursor:
        preferences[i[0]] = i[1]

    close_connection(cnx)

    return preferences


def set_user_preferences(user_id, **kwargs):
    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = (f"INSERT INTO user_preference VALUES ('{user_id}', 'timezone', '{kwargs.get('timezone')}')," +
                 f" ('{user_id}', 'reverse_order', '{kwargs.get('reverse_order')}')"
                 " ON DUPLICATE KEY UPDATE preference_value=CASE" +
                 f" WHEN preference_key = 'timezone' THEN '{kwargs.get('timezone')}'" +
                 f" WHEN preference_key = 'reverse_order' THEN '{kwargs.get('reverse_order')}'"
                 f" ELSE NULL END;")

    cursor.execute(sql_query)

    cnx.commit()
    close_connection(cnx)


def close_connection(cnx):

    return cnx.close()
