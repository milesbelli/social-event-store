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

    sql_fitbit_sleep = ("SELECT eventdate, eventtime, sleepid, logid, startdatetime, enddatetime, timezone,"
                        " duration, mainsleep FROM events e LEFT JOIN fitbit_sleep f"
                        " ON e.detailid = f.sleepid"
                        f" WHERE f.sleepid = {sleep_id} AND e.eventtype = 'fitbit-sleep'")

    output = get_results_for_query(sql_fitbit_sleep)

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


def insert_foursquare_checkins(checkins, user_prefs):

    cnx = create_connection('social')
    cursor = cnx.cursor()
    user_id = user_prefs.user_id

    checkin_values = list()
    event_values = list()

    # Query db to see what all is in the db already

    already_in_db = list()

    sql_get_already_in_db = (f"SELECT checkinid FROM events e LEFT JOIN foursquare_checkins f"
                             f" ON e.detailid = f.eventid"
                             f" WHERE e.userid = {user_id} AND e.eventtype = 'foursquare'")

    cursor.execute(sql_get_already_in_db)

    for i in cursor:
        if i:
            already_in_db.append(str(i[0]))


    # Pop entries from the dict which are already in the db

    for entry in already_in_db:
        checkins.pop(entry)

    # Each values entry will contain, in this order:
    # checkinid, eventtype, tzoffset, venueid
    for key in checkins:
        checkin = checkins[key]
        checkin_values.append(f"('{checkin['id']}', '{checkin['type']}', '{checkin['timeZoneOffset']}',"
                              f" '{checkin['venue']['id']}', '{checkin.get_venue_name_for_sql()}',"
                              f" '{checkin['createdAt']}', {checkin.get_shout_for_sql()},"
                              f" {checkin.get_event_id_for_sql()}, {checkin.get_event_name_for_sql()},"
                              f" {checkin.get_primary_category_id_and_name()['id']},"
                              f" {checkin.get_primary_category_id_and_name()['name']})")

    # Insert into db in 100 entry batches
    grouped_values = group_insert_into_db(checkin_values, 100)

    for events_to_insert in grouped_values:

        sql_insert_checkin_data = (f"INSERT INTO foursquare_checkins (checkinid, eventtype, tzoffset, venueid,"
                                   f" venuename, checkintime, shout, veventid, veventname, primarycatid, primarycatname)"
                                   f" VALUES {events_to_insert};")

        cursor.execute(sql_insert_checkin_data)


    sql_get_ids_for_events = (f"SELECT f.checkinid, f.eventid from foursquare_checkins f WHERE f.eventid NOT IN"
                              f" (SELECT e.detailid FROM events e WHERE e.eventtype = 'foursquare')")

    cursor.execute(sql_get_ids_for_events)

    event_id_dict = dict()

    # Result will be a dict with keys of checkinid and values of eventid, to use for events table detailid
    for i in cursor:
        event_id_dict[i[0]] = i[1]

    event_values = list()

    for key in checkins:
        checkin = checkins[key]
        event_id = event_id_dict[checkin["id"]]
        event_values.append(f"('{user_id}', '{checkin.get_date_str()}', '{checkin.get_time_str()}', 'foursquare',"
                            f" '{event_id}')")

    grouped_event_values = group_insert_into_db(event_values, 100)

    for events_to_insert in grouped_event_values:

        sql_insert_event_data = ("INSERT INTO events (userid, eventdate, eventtime, eventtype, detailid) "
                                f"VALUES {events_to_insert};")

        cursor.execute(sql_insert_event_data)

    cnx.commit()


def get_existing_tweets(cursor):
      
    sql_get_all_tweet_ids = "SELECT tweetid FROM tweetdetails;"

    cursor.execute(sql_get_all_tweet_ids)
    
    output = list()
    
    for i in cursor:
        output.append(str(i[0]))
    
    return output


def get_datetime_range(start_datetime, end_datetime, list_of_data_types):

    subquery_list = list()

    # TODO: This is not going to scale, so come up with a better way to handle this
    # 0 : eventdate
    # 1 : eventtime
    # 2 : detailid / logid
    # 3 : tweettext / shout
    # 4 : client
    # 5 : latitude
    # 6 : longitude
    # 7 : eventtype
    # 8 : enddatetime
    # 9 : sleepid
    # 10: sum(stageminutes)
    # 11: startdatetime
    # 12: replyid
    # 13: venuename
    # 14: venueid
    # 15: veventid
    # 16: veventname
    # 17: address
    # 18: city
    # 19: state
    # 20: country
    # 21: checkinid
    # 22: sleep_time
    # 23: timezone

    twitter_sql_query = ("SELECT eventdate date, eventtime time, detailid source_id, tweettext body, client, "
                         "latitude, longitude, eventtype object_type, NULL end_time, NULL sleep_id, NULL rest_mins,"
                         " NULL start_time, replyid reply_id, NULL venue_name, NULL venue_id, NULL venue_event_id,"
                         " NULL venue_event_name, NULL address, NULL city, NULL state, NULL country, NULL checkin_id,"
                         " NULL sleep_time, NULL timezone "
                         "FROM tweetdetails "
                         "LEFT JOIN events "
                         "ON detailid = tweetid "
                         "WHERE eventtype = 'twitter' "
                         f"AND CONCAT(eventdate,' ',eventtime) >= '{start_datetime}' "
                         f"AND CONCAT(eventdate,' ',eventtime) <= '{end_datetime}' ")

    fitbit_sql_query = ("SELECT eventdate date, eventtime time, f.logid source_id, NULL body, NULL client, "
                        "NULL latitude, NULL longitude, eventtype object_type, enddatetime end_time, f.sleepid sleep_id, "
                        "sum(stageminutes) rest_mins, startdatetime start_time, NULL reply_id, NULL venue_name, "
                        "NULL venue_id, NULL venue_event_id, NULL venue_event_name, NULL address, NULL city, "
                        "NULL state, NULL country, NULL checkin_id, f.duration sleep_time, f.timezone timezone "
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

    foursquare_sql_query = ("SELECT e.eventdate date, e.eventtime time, NULL source_id, o.shout body, NULL client, "
                            "v.latitude, v.longitude, e.eventtype object_type, NULL end_time, NULL sleep_id, "
                            "NULL rest_mins, NULL start_time, NULL reply_id, o.venuename venue_name, "
                            "o.venueid venue_id, o.veventid venue_event_id, o.veventname venue_event_name, "
                            "v.address address, v.city city, v.state state, v.country country, o.checkinid checkin_id, "
                            "NULL sleep_time, NULL timezone "
                            "FROM foursquare_checkins o "
                            "LEFT JOIN events e "
                            "ON e.detailid = o.eventid "
                            "LEFT JOIN foursquare_venues v "
                            "ON o.venueid = v.venueid "
                            "WHERE e.eventtype = 'foursquare' "
                            f"AND CONCAT(eventdate,' ',eventtime) >= '{start_datetime}' "
                            f"AND CONCAT(eventdate,' ',eventtime) <= '{end_datetime}' ")

    if 'twitter' in list_of_data_types:
        subquery_list.append(twitter_sql_query)

    if 'fitbit-sleep' in list_of_data_types:
        subquery_list.append(fitbit_sql_query)

    if "foursquare" in list_of_data_types:
        subquery_list.append(foursquare_sql_query)

    sql_query = " UNION ".join(subquery_list) + "ORDER BY date ASC, time ASC;"

    query_start_time = datetime.datetime.now()

    output = get_results_for_query(sql_query)

    print(f'Returned query in {datetime.datetime.now() - query_start_time}')

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

    sql_query = ("SELECT COUNT(*) count "
                 "FROM tweetdetails "
                 "LEFT JOIN events "
                 "ON detailid = tweetid "
                 "WHERE CONCAT(eventdate,' ',eventtime) >= '{}' "
                 "AND CONCAT(eventdate,' ',eventtime) <= '{}';".format(start_datetime, end_datetime))

    output = get_results_for_query(sql_query)

    return output


def generate_search_where_clause(search_list, searchable_columns):
    # Used by get_search_term. This generates the rather complicated where clause to
    # search for ALL search terms across ALL searchable columns. searchable_columns is
    # passed in as a list of all columns to coalesce into one searchable string

    where_clause = "WHERE "
    where_list = []
    coalesced_columns_list = []

    # The coalesce is a SQL way of converting NULL fields into blanks if they don't exist
    for column in searchable_columns:
        coalesced_columns_list.append(f"coalesce({column}, '')")

    # Coalesced columns can all be concatenated, even if one column is NULL. If these
    # weren't coalesced then one NULL would be make the whole thing NULL
    coalesced_columns = "concat(" + ", ' ',".join(coalesced_columns_list) + ")"

    # Each keyword needs to be evaluated separately and joined by ANDs because all keywords
    # must be contained somewhere in the searchable event data.
    for string in search_list:
        where_list.append(f"({coalesced_columns} like '%{string}%')")
    where_clause += " AND ".join(where_list)

    return where_clause


def get_search_term(search_term, event_types):

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

    search_list = search_term.split(" ")

    # The only searchable field in Twitter events is the text
    twitter_searchable = ["tweettext"]
    twitter_where_clause = generate_search_where_clause(search_list,  twitter_searchable)

    twitter_query = ("SELECT eventdate date, eventtime time, detailid source_id, tweettext body, client, "
                     "latitude, longitude, eventtype object_type, NULL end_time, NULL sleep_id, NULL rest_mins,"
                     " NULL start_time, replyid reply_id, NULL venue_name, NULL venue_id, NULL venue_event_id,"
                     " NULL venue_event_name, NULL address, NULL city, NULL state, NULL country, NULL checkin_id,"
                     " NULL sleep_time, NULL timezone "
                     "FROM tweetdetails "
                     "LEFT JOIN events "
                     "ON detailid = tweetid "
                     f"{twitter_where_clause} AND eventtype = 'twitter'"
                     f"{client_sql}"
                     f"{geo_sql}")

    # Quite a lot searchable for foursquare, including the "shout," the location, the venue, event name. A lot
    # of these would be NULL
    fsq_searchable = ["o.shout", "o.venuename", "o.veventname", "v.city", "v.state", "v.country"]
    fsq_where_clause = generate_search_where_clause(search_list,  fsq_searchable)

    foursquare_query = ("SELECT e.eventdate date, e.eventtime time, NULL source_id, o.shout body, NULL client, "
                        "v.latitude, v.longitude, e.eventtype object_type, NULL end_time, NULL sleep_id, "
                        "NULL rest_mins, NULL start_time, NULL reply_id, o.venuename venue_name, "
                        "o.venueid venue_id, o.veventid venue_event_id, o.veventname venue_event_name, "
                        "v.address address, v.city city, v.state state, v.country country, o.checkinid checkin_id, "
                        "NULL sleep_time, NULL timezone "
                        "FROM foursquare_checkins o "
                        "LEFT JOIN events e "
                        "ON e.detailid = o.eventid "
                        "LEFT JOIN foursquare_venues v "
                        "ON o.venueid = v.venueid "
                        f"{fsq_where_clause} AND e.eventtype = 'foursquare'")

    subqueries_list = []

    if "twitter" in event_types:
        subqueries_list.append(twitter_query)

    if "foursquare" in event_types and search_list != ['']:
        subqueries_list.append(foursquare_query)

    sql_query = " UNION ".join(subqueries_list) + "ORDER BY date ASC, time ASC;"

    output = get_results_for_query(sql_query)

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

    sql_query = f"SELECT preference_key, preference_value FROM user_preference WHERE userid = {user_id};"

    results = get_results_for_query(sql_query)

    preferences = dict()

    for result in results:
        preferences[result["preference_key"]] = result["preference_value"]

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


def set_user_source_preferences(user_id, **kwargs):
    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql_query = (f"INSERT INTO user_preference VALUES ('{user_id}', 'show_twitter', '{kwargs.get('show_twitter')}'),"
                 f" ('{user_id}', 'show_foursquare', '{kwargs.get('show_foursquare')}'), ('{user_id}', "
                 f"'show_fitbit-sleep', '{kwargs.get('show_fitbit-sleep')}')"
                 " ON DUPLICATE KEY UPDATE preference_value=CASE"
                 f" WHEN preference_key = 'show_twitter' THEN '{kwargs.get('show_twitter')}'"
                 f" WHEN preference_key = 'show_foursquare' THEN '{kwargs.get('show_foursquare')}'"
                 f" WHEN preference_key = 'show_fitbit-sleep' THEN '{kwargs.get('show_fitbit-sleep')}'"
                 f" ELSE NULL END;")

    cursor.execute(sql_query)
    cnx.commit()
    close_connection(cnx)


def insert_in_reply_to(tweet_id, create_date, user_name, in_reply_to_status, in_reply_to_user, status_text, user_id, lang):
    cnx = create_connection("social")
    cursor = cnx.cursor()

    # Both these can be empty, so we need to swap out for NULL
    in_reply_to_user = in_reply_to_user or "NULL"
    in_reply_to_status = in_reply_to_status or "NULL"

    # Drop timezone tag
    create_date = create_date.strip("Z")

    # format single quotes in status
    status_text = status_text.replace("'", "''")

    sql_query = ("INSERT INTO tweet_in_reply VALUES" +
                 f"({tweet_id}, '{create_date}', '{user_name}', {user_id}," +
                 f" {in_reply_to_status}, {in_reply_to_user}, '{status_text}', '{lang}');")

    cursor.execute(sql_query)
    cnx.commit()

    close_connection(cnx)


def get_in_reply_to(tweet_id):

    sql_query = f"SELECT tweetid, createdate, username, statustext FROM tweet_in_reply where tweetid = {tweet_id};"

    reply = get_results_for_query(sql_query)

    for result in reply:
        output = {"id_str": str(result["tweetid"]),
                  "created_date": result["createdate"],
                  "user": {"screen_name": result["username"]},
                  "text": result["statustext"]}
        return output
    else:
        return None


def insert_foursquare_venue(venue_id, **kwargs):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    name = kwargs.get("name").replace("'","''") if kwargs.get("name") else None
    name = f"'{name}'" if name else "NULL"
    url = f"'{kwargs.get('url')}'" if kwargs.get("url") else "NULL"
    address = kwargs.get("address").replace("'", "''") if kwargs.get("address") else None
    address = f"'{address}'" if address else "NULL"
    postal_code = f"'{kwargs.get('postal_code')}'" if kwargs.get('postal_code') else "NULL"
    cc = f"'{kwargs.get('cc')}'" if kwargs.get('cc') else "NULL"
    city = kwargs.get("city").replace("'", "''") if kwargs.get("city") else None
    city = f"'{city}'" if city else "NULL"
    state = kwargs.get("state").replace("'", "''") if kwargs.get("state") else None
    state = f"'{state}'" if state else "NULL"
    country = kwargs.get("country").replace("'", "''") if kwargs.get("country") else None
    country = f"'{country}'" if country else "NULL"
    latitude = f'{kwargs.get("latitude")}' if kwargs.get("latitude") else "NULL"
    longitude = f'{kwargs.get("longitude")}' if kwargs.get("longitude") else "NULL"

    sql_statement = (f"INSERT INTO foursquare_venues VALUES" +
                     f" ('{venue_id}', {name}, {url}, {address}, {postal_code}, {cc}, {city}, {state}, {country}, " +
                     f"{latitude}, {longitude})")

    cursor.execute(sql_statement)

    cnx.commit()

    close_connection(cnx)


def get_foursquare_venue(venue_id):

    sql_query = f"SELECT * FROM foursquare_venues WHERE venueid = '{venue_id}'"

    return get_results_for_query(sql_query)


def get_results_for_query(sql_query):

    print(f"Fetching results for query:\n{sql_query}")

    cnx = create_connection("social")
    cursor = cnx.cursor()

    cursor.execute(sql_query)

    results = cursor.fetchall()

    result_list = list()

    for row in results:
        result_dict = dict()

        for i in range(0, len(row)):
            result_dict[cursor.column_names[i]] = row[i]
        result_list.append(result_dict)

    close_connection(cnx)
    print(f"Returning {len(result_list)} result(s)")

    return result_list


def close_connection(cnx):

    return cnx.close()
