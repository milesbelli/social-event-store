import mysql.connector
import datetime
import common, secure


def create_connection(dbname):

    db_host = secure.host() or "127.0.0.1"
    
    cnx = mysql.connector.connect(user=secure.username(),
                                  password=secure.password(),
                                  host=db_host)
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

    print(f"[{datetime.datetime.now()}] Beginning to store sleep events, total of {len(sleep)} records to process.")
    proc_start_time = datetime.datetime.now()

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
            list_of_stages_values = list()

            for level in sleep_levels[log_id]["summary"]:

                count = sleep_levels[log_id]["summary"][level].get("count")
                minutes = sleep_levels[log_id]["summary"][level].get("minutes")
                avg_minutes = sleep_levels[log_id]["summary"][level].get("thirtyDayAvgMinutes") or 0

                # The "values" section of the sql statement will go on a list to be grouped in an optimal size
                stages_values = f"('{logid_index[log_id]}', '{level}', '{count}', '{minutes}', '{avg_minutes}')"
                list_of_stages_values.append(stages_values)

            list_of_stages_values = group_insert_into_db(list_of_stages_values, 10)

            for stages_values in list_of_stages_values:

                sql_add_stages = ("INSERT INTO fitbit_sleep_stages (sleepid, sleepstage, stagecount,"
                                  " stageminutes, avgstageminutes)"
                                  f" VALUES {stages_values}")

                cursor.execute(sql_add_stages)

            list_of_data_values = list()

            for item in sleep_levels[log_id]["data"]:

                sleep_date_time = item["dateTime"]
                level = item["level"]
                seconds = item["seconds"]

                # group data "values" to be optimal
                data_values = f"('{logid_index[log_id]}', '{sleep_date_time}', '{level}', '{seconds}')"
                list_of_data_values.append(data_values)

            list_of_data_values = group_insert_into_db(list_of_data_values, 100)

            for data_values in list_of_data_values:

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

    print(f"[{datetime.datetime.now()}] Finished processing all events, time elapsed was {datetime.datetime.now() - proc_start_time}")


def get_fitbit_sleep_event(sleep_id):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_fitbit_sleep = ("SELECT eventdate, eventtime, sleepid, logid, startdatetime, enddatetime, timezone,"
                        " duration, mainsleep FROM events e LEFT JOIN fitbit_sleep f"
                        " ON e.detailid = f.sleepid"
                        f" WHERE f.sleepid = {sleep_id} AND e.eventtype = 'fitbit-sleep'")

    cursor.execute(sql_fitbit_sleep)

    output = cursor.fetchone()

    close_connection(cnx)

    return output


def update_fitbit_sleep_timezone(sleep_id, event_date, event_time, timezone):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_event_update = (f"UPDATE events SET eventdate = '{event_date}', eventtime = '{event_time}'"
                        f" WHERE detailid = {sleep_id} and eventtype = 'fitbit-sleep'")

    cursor.execute(sql_event_update)

    sql_fitbit_sleep_update = (f"UPDATE fitbit_sleep SET timezone = '{timezone}'"
                               f" WHERE sleepid = {sleep_id}")

    cursor.execute(sql_fitbit_sleep_update)

    cnx.commit()
    close_connection(cnx)


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


def get_datetime_range(start_datetime, end_datetime, list_of_data_types):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    subquery_list = list()

    # 0 : eventdate
    # 1 : eventtime
    # 2 : detailid / logid
    # 3 : tweettext / duration
    # 4 : client / timezone
    # 5 : latitude
    # 6 : longitude
    # 7 : eventtype
    # 8 : enddatetime
    # 9 : sleepid
    # 10: sum(stageminutes)
    # 11: startdatetime
    # 12: replyid

    twitter_sql_query = ("SELECT eventdate, eventtime, detailid, tweettext, client, "
                         "latitude, longitude, eventtype, NULL, NULL, NULL, NULL, replyid "
                         "FROM tweetdetails "
                         "LEFT JOIN events "
                         "ON detailid = tweetid "
                         "WHERE eventtype = 'twitter' "
                         f"AND CONCAT(eventdate,' ',eventtime) >= '{start_datetime}' "
                         f"AND CONCAT(eventdate,' ',eventtime) <= '{end_datetime}' ")

    fitbit_sql_query = ("SELECT eventdate, eventtime, f.logid, f.duration, f.timezone, NULL, NULL, "
                        "eventtype, enddatetime, f.sleepid, sum(stageminutes), startdatetime, NULL "
                        "FROM fitbit_sleep f "
                        "LEFT JOIN events "
                        "ON detailid = f.sleepid "
                        "LEFT JOIN fitbit_sleep_stages s "
                        "ON f.sleepid = s.sleepid "
                        "WHERE eventtype = 'fitbit-sleep' "
                        f"AND CONCAT(eventdate,' ',eventtime) >= '{start_datetime}' "
                        f"AND CONCAT(eventdate,' ',eventtime) <= '{end_datetime}' "
                        f"AND sleepstage NOT LIKE '%wake' AND sleepstage NOT LIKE 'restless' "
                        f"GROUP BY s.sleepid, eventdate, eventtime, f.logid, f.duration, f.timezone, f.sleepid ")

    if 'twitter' in list_of_data_types:
        subquery_list.append(twitter_sql_query)

    if 'fitbit-sleep' in list_of_data_types:
        subquery_list.append(fitbit_sql_query)

    sql_query = " UNION ".join(subquery_list) + "ORDER BY eventdate ASC, eventtime ASC;"

    query_start_time = datetime.datetime.now()
    cursor.execute(sql_query)

    print(f'Returned query:\n{sql_query}\n in {datetime.datetime.now() - query_start_time}')

    output = list()

    for i in cursor:
        output.append(i)

    close_connection(cnx)

    return output


def group_insert_into_db(list_of_rows, group_size):
    """It is far more optimal to insert multiple values with a single SQL statement. However, it is possible to create
    statements which are too large and cause an error. The workaround for this is to divide the values into chunks which
    are large enough to be optimal while being small enough to avoid an error.
    This function takes both the list of values and a size parameter, to adjust the size of each group."""

    list_pos = 0
    sub_list = list()
    combined_list = list()

    # Iterate through the whole list of items
    while list_pos < len(list_of_rows):

        # Start building a sub-list to later add
        if len(sub_list) < group_size:
            sub_list.append(list_of_rows[list_pos])

        # Once the sub-list is "full" it is dumped onto the return list
        else:
            combined_list.append(", ".join(sub_list))
            sub_list = list()
            sub_list.append(list_of_rows[list_pos])

        list_pos += 1

    # Whatever was on the sub-list when the loop ended gets added
    if len(sub_list) > 0:
        combined_list.append(", ".join(sub_list))

    return combined_list


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

    def keyword_parse(keyword):

        if keyword in search_term:
            try:
                keyword_index = search_term.index(keyword)
                open_quote_index = search_term.index("\"", keyword_index)
                closed_quote_index = search_term.index("\"", open_quote_index + 1)
                keyword_search = search_term[open_quote_index + 1:closed_quote_index]

                modified_search = search_term[:keyword_index] + search_term[closed_quote_index + 1:]

            except ValueError as error:
                print(f"Error while parsing keyword: {error}")
                keyword_search = str()
                modified_search = search_term

        else:
            keyword_search = str()
            modified_search = search_term

        return keyword_search, modified_search

    client_search, search_term = keyword_parse("client:\"")
    client_sql = f"AND client like '%{client_search}%' " if client_search else str()

    geo_search, search_term = keyword_parse("geo:")
    geo_sql = f"AND latitude IS NOT NULL AND longitude IS NOT NULL " if geo_search == "true" else \
        f"AND latitude IS NULL AND longitude IS NULL " if geo_search == "false" else str()

    sql_query = ("SELECT eventdate, eventtime, detailid, tweettext, client, latitude, longitude, eventtype, "
                 "NULL, NULL, NULL, NULL, replyid "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 f"WHERE tweettext LIKE '%{search_term}%' "
                 f"{client_sql}"
                 f"{geo_sql}"
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


def insert_in_reply_to(tweet_id, create_date, user_name, in_reply_to_user, status_text, user_id, lang):
    cnx = create_connection("social")
    cursor = cnx.cursor()

    in_reply_to_user = in_reply_to_user or "NULL"

    # Drop timezone tag
    create_date = create_date.strip("Z")

    # format single quotes in status
    status_text = status_text.replace("'", "''")


    sql_query = ("INSERT INTO tweet_in_reply VALUES" +
                 f"({tweet_id}, '{create_date}', '{user_name}', {user_id}," +
                 f" {in_reply_to_user}, '{status_text}', '{lang}');")

    cursor.execute(sql_query)
    cnx.commit()

    close_connection(cnx)


def get_in_reply_to(tweet_id):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = (f"SELECT tweetid, createdate, username, statustext FROM tweet_in_reply where tweetid = {tweet_id};")

    cursor.execute(sql_query)

    reply = cursor.fetchone()

    if reply:
        output = {"id_str": str(reply[0]),
                  "created_date": reply[1],
                  "user": {"screen_name": reply[2]},
                  "text": reply[3]}
        return output
    else:
        return None


def close_connection(cnx):

    return cnx.close()
