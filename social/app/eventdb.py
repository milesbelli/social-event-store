import mysql.connector
import datetime
import common
import os


def create_connection(dbname):

    db_host = os.getenv("DB_HOST") or "127.0.0.1"

    cnx = mysql.connector.connect(user=os.getenv("DB_USER"),
                                  password=os.getenv("DB_PASS"),
                                  host=db_host,
                                  db=dbname)
    cnx.set_charset_collation("utf8mb4", "utf8mb4_general_ci")

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

            tweet_text = list_of_tweets[i]["text"].replace("'", "''")
            user_id = list_of_tweets[i]['user']['id']
            lat = list_of_tweets[i]["latitude"]
            lon = list_of_tweets[i]["longitude"]
            reply_id = list_of_tweets[i]["in_reply_to_status_id"]
            client = list_of_tweets[i]["client_name"]
            rt_id = list_of_tweets[i]["rt_id"]

            value_to_append = (f"('{tweet_id}','{'1'}','{tweet_text}'"
                               f",'{user_id}',{lat},{lon},{reply_id},"
                               f"'{client}',{rt_id})")

            values_tweets += value_to_append

            sql_date = list_of_tweets[i]["sql_date"]
            sql_time = list_of_tweets[i]["sql_time"]

            value_to_append = (f"('{'1'}','{sql_date}','{sql_time}',"
                               f"'{sql_date + ' ' + sql_time}','twitter',"
                               f"'{tweet_id}')")

            values_events += value_to_append

            for hashtag in list_of_tweets[i]["entities"]["hashtags"]:

                start_idx = hashtag["indices"][0]
                tag_text = hashtag["text"]

                value_to_append = f"('{tweet_id}','{start_idx}','{tag_text}')"

                if len(values_hashtags) > 0:
                    values_hashtags += ","

                values_hashtags += value_to_append

        else:
            # Tweet is in db, so add to duplicate list for checking
            duplicate_dict[str(list_of_tweets[i]["id"])] = list_of_tweets[i]
            values_duplicates = tweet_id if len(values_duplicates) == 0 else \
                values_duplicates + ", " + tweet_id

    if len(values_tweets) > 0:
    
        sql_insert_tweets = ("INSERT INTO tweetdetails"
                             "(tweetid, userid, tweettext, twitteruserid, latitude, longitude, replyid, client, retweetid)"
                             "VALUES {}".format(values_tweets))
        
        cursor.execute(sql_insert_tweets)
        
    if len(values_events) > 0:
    
        sql_insert_events = ("INSERT INTO events"
                             "(userid, eventdate, eventtime, eventdt, eventtype, detailid)"
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
    user_id = user_prefs.user_id
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

            event_values += f"('{user_id}', '{event_date}', '{event_time}', '{event_date} {event_time}', 'fitbit-sleep', '{event_id}')"

        sql_add_new_to_events_utc = ("INSERT INTO events (userid, eventdate, eventtime, eventdt, eventtype, detailid) "
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

    sql_event_update = (f"UPDATE events SET eventdate = '{event_date}', eventtime = '{event_time}', "
                        f"eventdt = '{event_date} {event_time}'"
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
        event_values.append(f"('{user_id}', '{checkin.get_date_str()}', '{checkin.get_time_str()}',"
                            f" '{checkin.get_date_str()} {checkin.get_time_str()}', 'foursquare',"
                            f" '{event_id}')")

    grouped_event_values = group_insert_into_db(event_values, 100)

    for events_to_insert in grouped_event_values:

        sql_insert_event_data = ("INSERT INTO events (userid, eventdate, eventtime, eventdt, eventtype, detailid) "
                                f"VALUES {events_to_insert};")

        cursor.execute(sql_insert_event_data)

    cnx.commit()


def insert_sms_into_db(sms_messages, user_prefs):
    user_id = user_prefs.user_id
    cnx = create_connection('social')
    cursor = cnx.cursor()

    already_in_db = list()

    sql_get_already_in_db = (f"SELECT fingerprint FROM events e LEFT JOIN sms_messages m"
                             f" ON e.detailid = m.smsid"
                             f" WHERE e.userid = {user_id} AND e.eventtype = 'sms'")

    cursor.execute(sql_get_already_in_db)

    for i in cursor:
        if i:
            already_in_db.append(str(i[0]))

    # Pop entries from the dict which are already in the db

    for entry in already_in_db:
        if sms_messages.get(entry):
            sms_messages.pop(entry)

    sql_values = list()

    contacts_dict = {}

    for key in sms_messages:
        message = sms_messages[key]

        sql_row = (f"('{user_id}', '{message['id']}', {message.get_sql('type')}, {message.get_sql('conversation')},"
                   f"{message.get_sql('contact_num')}, {message.sql_body()}, {message.get_sql('folder')})")

        sql_values.append(sql_row)

        if message.get("contact_name") \
                and message.get_sql("contact_num") \
                and not contacts_dict.get(message.get("contact_num")):
            contacts_dict[message.get("contact_num")] = message.get_sql("contact_name")

    grouped_values = group_insert_into_db(sql_values, 500)

    for events_to_insert in grouped_values:

        sql_insert_sms_msg = (f"INSERT INTO sms_messages ( userid, fingerprint, type, conversation, contact_num,"
                                   f" body, folder )"
                                   f" VALUES {events_to_insert};")

        cursor.execute(sql_insert_sms_msg)

    sql_sms_with_no_datetime = (f"SELECT fingerprint, smsid FROM sms_messages where userid = '{user_id}' AND "
                                f"smsid NOT IN (SELECT detailid FROM events where userid = '{user_id}' AND "
                                f"eventtype = 'sms');")

    cursor.execute(sql_sms_with_no_datetime)

    event_id_dict = dict()

    # Result will be a dict with keys of checkinid and values of eventid, to use for events table detailid
    for i in cursor:
        event_id_dict[i[0]] = i[1]

    event_values = list()

    for key in sms_messages:
        message = sms_messages[key]
        sms_id = event_id_dict[key]

        event_values.append(f"('{user_id}', '{message['date']}', '{message['time']}', "
                            f"'{message['date']} {message['time']}', 'sms', {sms_id})")

    grouped_event_values = group_insert_into_db(event_values, 100)

    for events_to_insert in grouped_event_values:

        sql_insert_event_data = ("INSERT INTO events (userid, eventdate, eventtime, eventdt, eventtype, detailid) "
                                f"VALUES {events_to_insert};")

        cursor.execute(sql_insert_event_data)

    # Add in contacts based on the option contact_name key

    sql_contacts_extant = ("SELECT contact_num FROM sms_contacts "
                           f"WHERE userid = {user_id}")

    cursor.execute(sql_contacts_extant)

    existing_contacts = list()

    for i in cursor:
        existing_contacts.append(i[0])

    for contact in existing_contacts:
        if contacts_dict.get(contact):
            contacts_dict.pop(contact)

    contacts_values = list()

    for key in contacts_dict:
        contact = contacts_dict[key]

        contacts_values.append(f"('{user_id}', '{key}', {contact})")

    grouped_contacts_values = group_insert_into_db(contacts_values, 100)

    for contacts_to_insert in grouped_contacts_values:
        sql_insert_contacts = ("INSERT INTO sms_contacts (userid, contact_num, contact_name) "
                               f"VALUES {contacts_to_insert}")
        cursor.execute(sql_insert_contacts)

    cnx.commit()


def get_existing_tweets(cursor):
      
    sql_get_all_tweet_ids = "SELECT tweetid FROM tweetdetails;"

    cursor.execute(sql_get_all_tweet_ids)
    
    output = list()
    
    for i in cursor:
        output.append(str(i[0]))
    
    return output


def create_select_cols(all_cols, specific_cols):

    select_cols = list()

    for col in all_cols:
        col_pair = str()
        if specific_cols.get(col):
            col_pair = f"{specific_cols[col]} AS {col}"
        else:
            col_pair = f"NULL AS {col}"

        select_cols.append(col_pair)

    select_string = ", ".join(select_cols)

    return select_string


def get_datetime_range(start_datetime, end_datetime, list_of_data_types, user_prefs):

    subquery_list = list()

    user_id = user_prefs.user_id

    all_columns = [
        "date",
        "time",
        "source_id",
        "body",
        "client",
        "latitude",
        "longitude",
        "object_type",
        "end_time",
        "sleep_id",
        "rest_mins",
        "start_time",
        "reply_id",
        "venue_name",
        "venue_id",
        "venue_event_id",
        "venue_event_name",
        "address",
        "city",
        "state",
        "country",
        "checkin_id",
        "sleep_time",
        "timezone",
        "conversation",
        "contact_num",
        "folder",
        "fingerprint",
        "contact_name",
        "game_title",
        "trophy_name"
    ]

    twitter_columns = {
        "date": "eventdate",
        "time":  "eventtime",
        "source_id": "detailid",
        "body": "tweettext",
        "client": "client",
        "latitude": "latitude",
        "longitude": "longitude",
        "object_type": "eventtype"
    }

    twitter_select = create_select_cols(all_columns, twitter_columns)

    twitter_sql_query = (f"SELECT {twitter_select} "
                         "FROM events "
                         "LEFT JOIN tweetdetails "
                         "ON detailid = tweetid "
                         "WHERE eventtype = 'twitter' "
                         f"AND eventdt >= '{start_datetime}' "
                         f"AND eventdt <= '{end_datetime}' "
                         f"AND events.userid = '{user_id}' ")

    fitbit_columns = {
        "date": "eventdate",
        "time":  "eventtime",
        "source_id": "f.logid",
        "object_type": "eventtype",
        "end_time": "enddatetime",
        "sleep_id": "f.sleepid",
        "rest_mins": "sum(stageminutes)",
        "start_time": "startdatetime",
        "sleep_time": "f.duration",
        "timezone": "f.timezone"
    }

    fitbit_select = create_select_cols(all_columns, fitbit_columns)

    fitbit_sql_query = (f"SELECT {fitbit_select} "
                        "FROM events "
                        "LEFT JOIN fitbit_sleep f "
                        "ON detailid = f.sleepid "
                        "LEFT JOIN fitbit_sleep_stages s "
                        "ON f.sleepid = s.sleepid "
                        "WHERE eventtype = 'fitbit-sleep' "
                        f"AND eventdt >= '{start_datetime}' "
                        f"AND eventdt <= '{end_datetime}' "
                        f"AND events.userid = '{user_id}' "
                        f"AND sleepstage NOT LIKE '%wake' AND sleepstage NOT LIKE 'restless' "
                        f"GROUP BY s.sleepid, eventdate, eventtime, f.logid, f.duration, f.timezone, f.sleepid ")

    foursquare_columns = {
        "date": "e.eventdate",
        "time": "e.eventtime",
        "body": "o.shout",
        "latitude": "v.latitude",
        "longitude": "v.longitude",
        "object_type": "e.eventtype",
        "venue_name": "o.venuename",
        "venue_id": "o.venueid",
        "venue_event_id": "o.veventid",
        "venue_event_name": "o.veventname",
        "address": "v.address",
        "city": "v.city",
        "state": "v.state",
        "country": "v.country",
        "checkin_id": "o.checkinid"
    }

    foursquare_select = create_select_cols(all_columns, foursquare_columns)

    foursquare_sql_query = (f"SELECT {foursquare_select} "
                            "FROM events e "
                            "LEFT JOIN foursquare_checkins o "
                            "ON e.detailid = o.eventid "
                            "LEFT JOIN foursquare_venues v "
                            "ON o.venueid = v.venueid "
                            "WHERE e.eventtype = 'foursquare' "
                            f"AND eventdt >= '{start_datetime}' "
                            f"AND eventdt <= '{end_datetime}' "
                            f"AND e.userid = '{user_id}' ")

    sms_columns = {
        "date": "e.eventdate",
        "time": "e.eventtime",
        "body": "s.body",
        "object_type": "e.eventtype",
        "conversation": "s.conversation",
        "contact_num": "s.contact_num",
        "folder": "s.folder",
        "fingerprint": "s.fingerprint",
        "contact_name": "c.contact_name"
    }

    sms_select = create_select_cols(all_columns, sms_columns)

    sms_sql_query = (f"SELECT {sms_select} "
                     "FROM events e "
                     "lEFT JOIN sms_messages s "
                     "ON e.detailid = s.smsid "
                     "LEFT JOIN sms_contacts c "
                     "ON s.contact_num = c.contact_num AND s.userid = c.userid "
                     "WHERE e.eventtype = 'sms' "
                     f"AND eventdt >= '{start_datetime}' "
                     f"AND eventdt <= '{end_datetime}' "
                     f"AND e.userid = '{user_id}' ")

    psn_sql_query = (
        f"""
        SELECT
        date(e.earned_date_time) date,
        time(e.earned_date_time) time,
        NULL source_id,
        g.trophy_detail body,
        s.platform client,
        NULL latitude,
        NULL longitude,
        "psn" object_type,
        NULL end_time,
        NULL sleep_id,
        NULL rest_mins,
        NULL start_time,
        NULL reply_id,
        NULL venue_name,
        NULL venue_id,
        NULL venue_event_id,
        NULL venue_event_name,
        NULL address,
        NULL city,
        NULL state,
        NULL country,
        NULL checkin_id,
        NULL sleep_time,
        NULL timezone,
        NULL conversation,
        NULL contact_num,
        NULL folder,
        NULL fingerprint,
        NULL contact_name,
        s.game_title game_title,
        g.trophy_name trophy_name
        FROM psn_earned_trophies AS e
        LEFT JOIN psn_game_trophies AS g
        ON e.game_id = g.game_id AND e.trophy_id = g.trophy_id
        AND e.trophy_set_version = g.trophy_set_version
        LEFT JOIN psn_summary AS s
        ON s.game_id = e.game_id AND s.userid = e.userid
        AND s.trophy_set_version = e.trophy_set_version
        WHERE
        e.earned_date_time >= '{start_datetime}'
        AND e.earned_date_time <= '{end_datetime}'
        AND e.userid = {user_id}
        """
    )

    if 'twitter' in list_of_data_types:
        subquery_list.append(twitter_sql_query)

    if 'fitbit-sleep' in list_of_data_types:
        subquery_list.append(fitbit_sql_query)

    if "foursquare" in list_of_data_types:
        subquery_list.append(foursquare_sql_query)

    if "sms" in list_of_data_types:
        subquery_list.append(sms_sql_query)

    if "psn" in list_of_data_types:
        subquery_list.append(psn_sql_query)

    output = list()

    if len(list_of_data_types) > 0:

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


def get_search_term(search_term, user_prefs, event_types):

    user_id = user_prefs.user_id

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

    twitter_query = ("SELECT e.eventdate date, e.eventtime time, e.detailid source_id, tweettext body, client, "
                     "latitude, longitude, e.eventtype object_type, NULL end_time, NULL sleep_id, NULL rest_mins,"
                     " NULL start_time, replyid reply_id, NULL venue_name, NULL venue_id, NULL venue_event_id,"
                     " NULL venue_event_name, NULL address, NULL city, NULL state, NULL country, NULL checkin_id,"
                     " NULL sleep_time, NULL timezone, NULL conversation, NULL contact_num, "
                     "NULL folder, NULL fingerprint, NULL contact_name, NULL game_title, NULL trophy_name "
                     "FROM tweetdetails "
                     "LEFT JOIN events e "
                     "ON detailid = tweetid "
                     f"{twitter_where_clause} AND eventtype = 'twitter' AND e.userid = '{user_id}'"
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
                        "NULL sleep_time, NULL timezone, NULL conversation, NULL contact_num, "
                        "NULL folder, NULL fingerprint, NULL contact_name, NULL game_title, NULL trophy_name "
                        "FROM foursquare_checkins o "
                        "LEFT JOIN events e "
                        "ON e.detailid = o.eventid "
                        "LEFT JOIN foursquare_venues v "
                        "ON o.venueid = v.venueid "
                        f"{fsq_where_clause} AND e.eventtype = 'foursquare' AND e.userid = '{user_id}'")

    sms_searchable = ["s.body"]
    sms_where_clause = generate_search_where_clause(search_list, sms_searchable)

    sms_query = ("SELECT e.eventdate date, e.eventtime time, NULL source_id, s.body body, NULL client, "
                 "NULL latitude, NULL longitude, e.eventtype object_type, NULL end_time, NULL sleep_id, "
                 "NULL rest_mins, NULL start_time, NULL reply_id, NULL venue_name, "
                 "NULL venue_id, NULL venue_event_id, NULL venue_event_name, "
                 "NULL address, NULL city, NULL state, NULL country, NULL checkin_id, "
                 "NULL sleep_time, NULL timezone, s.conversation conversation, s.contact_num contact_num, "
                 "s.folder folder, s.fingerprint fingerprint, c.contact_name contact_name, NULL game_title, "
                 "NULL trophy_name "
                 "FROM sms_messages s "
                 "LEFT JOIN events e "
                 "ON e.detailid = s.smsid "
                 "LEFT JOIN sms_contacts c "
                 "ON c.contact_num = s.contact_num AND s.userid = c.userid "
                 f"{sms_where_clause} AND e.eventtype = 'sms' AND e.userid = '{user_id}'")

    psn_searchable = ["g.trophy_detail", "s.platform", "s.game_title", "g.trophy_name"]
    psn_where_clause = generate_search_where_clause(search_list, psn_searchable)

    psn_query = (
        f"""
        SELECT
        date(e.earned_date_time) date,
        time(e.earned_date_time) time,
        NULL source_id,
        g.trophy_detail body,
        s.platform client,
        NULL latitude,
        NULL longitude,
        "psn" object_type,
        NULL end_time,
        NULL sleep_id,
        NULL rest_mins,
        NULL start_time,
        NULL reply_id,
        NULL venue_name,
        NULL venue_id,
        NULL venue_event_id,
        NULL venue_event_name,
        NULL address,
        NULL city,
        NULL state,
        NULL country,
        NULL checkin_id,
        NULL sleep_time,
        NULL timezone,
        NULL conversation,
        NULL contact_num,
        NULL folder,
        NULL fingerprint,
        NULL contact_name,
        s.game_title game_title,
        g.trophy_name trophy_name
        FROM psn_earned_trophies AS e
        LEFT JOIN psn_game_trophies AS g
        ON e.game_id = g.game_id AND e.trophy_id = g.trophy_id
        AND e.trophy_set_version = g.trophy_set_version
        LEFT JOIN psn_summary AS s
        ON s.game_id = e.game_id AND s.userid = e.userid
        AND s.trophy_set_version = e.trophy_set_version
        {psn_where_clause}
        AND earned_date_time IS NOT NULL
        AND e.userid = {user_id}
        """
    )

    subqueries_list = []

    if "twitter" in event_types:
        subqueries_list.append(twitter_query)

    if "foursquare" in event_types and search_list != [""]:
        subqueries_list.append(foursquare_query)

    if "sms" in event_types and search_list != [""]:
        subqueries_list.append(sms_query)

    if "psn" in event_types and search_list != [""]:
        subqueries_list.append(psn_query)

    sql_query = " UNION ".join(subqueries_list) + "ORDER BY date ASC, time ASC;"

    if len(subqueries_list) > 0:
        output = get_results_for_query(sql_query)
    else:
        output = []

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

    sql_query = (f"INSERT INTO user_preference VALUES "
                 f"('{user_id}', 'show_twitter', '{kwargs.get('show_twitter')}'),"
                 f" ('{user_id}', 'show_foursquare', '{kwargs.get('show_foursquare')}'), "
                 f"('{user_id}', 'show_fitbit-sleep', '{kwargs.get('show_fitbit-sleep')}'), "
                 f"('{user_id}', 'show_sms', '{kwargs.get('show_sms')}'), "
                 f"('{user_id}', 'show_psn', '{kwargs.get('show_psn')}')"
                 " ON DUPLICATE KEY UPDATE preference_value=CASE"
                 f" WHEN preference_key = 'show_twitter' THEN '{kwargs.get('show_twitter')}'"
                 f" WHEN preference_key = 'show_foursquare' THEN '{kwargs.get('show_foursquare')}'"
                 f" WHEN preference_key = 'show_fitbit-sleep' THEN '{kwargs.get('show_fitbit-sleep')}'"
                 f" WHEN preference_key = 'show_sms' THEN '{kwargs.get('show_sms')}'"
                 f" WHEN preference_key = 'show_psn' THEN '{kwargs.get('show_psn')}'"
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

    cursor_time = datetime.datetime.now()

    cursor.execute(sql_query)

    print(f"Cursor exec time: {datetime.datetime.now() - cursor_time}")

    result_timer = datetime.datetime.now()

    results = cursor.fetchall()

    result_list = list()

    for row in results:
        result_dict = dict()

        for i in range(0, len(row)):
            result_dict[cursor.column_names[i]] = row[i]
        result_list.append(result_dict)

    print(f"Results parse time: {datetime.datetime.now() - result_timer}")

    close_connection(cnx)
    print(f"Returning {len(result_list)} result(s)")

    return result_list


def edit_contact(contact_info, user_prefs):
        cnx = create_connection("social")
        cursor = cnx.cursor()

        user_id = user_prefs.user_id
        contact_num = contact_info.get("contact_num")
        new_name = contact_info.get("contact_name")

        update_sql = f"UPDATE sms_contacts SET contact_name = '{new_name}' WHERE userid = '{user_id}' " \
                     f"AND contact_num = {contact_num}"

        new_save_sql = f"INSERT INTO sms_contacts VALUES ('{user_id}', '{contact_num}', '{new_name}');"

        already_existing_sql = f"SELECT count(*) contact_ct FROM sms_contacts WHERE userid = '{user_id}' AND " \
                               f"contact_num = '{contact_num}';"

        check = get_results_for_query(already_existing_sql)

        # If it exists, run update query, else run insert
        if check[0].get("contact_ct") == 1:
            cursor.execute(update_sql)

        else:
            cursor.execute(new_save_sql)

        cnx.commit()
        close_connection(cnx)


def edit_timestamp_for_event(event_id, event_type, time, date, user_prefs, connection=None):

    cnx = connection or create_connection("social")
    cursor = cnx.cursor()

    user_id = user_prefs.user_id

    update_time_sql = f"UPDATE events SET eventdate = '{date}', eventtime = '{time}', eventdt = '{date} {time}'" \
                      f" WHERE detailid = '{event_id}' AND eventtype = '{event_type}' AND userid = '{user_id}';"

    cursor.execute(update_time_sql)

    cnx.commit()

    if not connection:
        close_connection(cnx)


def delete_item_from_db(item_id, item_type):
    type_dict = {"sms": {"sms_messages": "smsid"},
                 "twitter": {"tweetdetails": "tweetid",
                             "tweetconflicts": "tweetid",
                             "tweethashtags": "tweetid",
                             "tweetmedia": "tweetid",
                             "tweeturls": "tweetid"},
                 "foursquare": {"foursquare_checkins": "eventid"},
                 "fitbit-sleep": {"fitbit_sleep": "sleepid",
                                  "fitbit_sleep_data": "sleepid",
                                  "fitbit_sleep_stages": "sleepid"}}

    list_of_sqls = list()

    tables = type_dict[item_type]
    for table in tables:
        list_of_sqls.append(
            f"DELETE FROM {table} WHERE {tables[table]} = '{item_id}';"
        )

    list_of_sqls.append(
        f"DELETE FROM events WHERE detailid = '{item_id}' and eventtype = '{item_type}';"
    )

    cnx = create_connection("social")
    cursor = cnx.cursor()

    for sql in list_of_sqls:
        cursor.execute(sql)

    cnx.commit()


def get_conversation(conversation, start, length, user_prefs):

    user_id = user_prefs.user_id

    sms_query = ("SELECT e.eventdate date, e.eventtime time, s.body body, "
                 "e.eventtype object_type, "
                 "s.conversation conversation, s.contact_num contact_num, "
                 "s.folder folder, s.fingerprint fingerprint, "
                 "c.contact_name contact_name, NULL source_id "
                 "FROM events e "
                 "LEFT JOIN sms_messages s "
                 "ON e.detailid = s.smsid "
                 "LEFT JOIN sms_contacts c "
                 "ON s.contact_num = c.contact_num AND s.userid = c.userid "
                 "WHERE e.eventtype = 'sms' "
                 f"AND eventdt <= '{start}' "
                 f"AND e.userid = '{user_id}' "
                 f"AND (s.conversation = '{conversation}' "
                 f"OR (s.conversation IS NULL and s.contact_num = '{conversation}')) "
                 "ORDER BY eventdt DESC "
                 f"LIMIT {length} ")

    output = get_results_for_query(sms_query)

    return output

def get_previous_conversation(conversation, start, length, user_prefs):
    user_id = user_prefs.user_id

    sms_query = ("SELECT s.eventdt eventdt FROM "
                "(SELECT e.eventdt eventdt "
                "FROM events e LEFT JOIN sms_messages s "
                "ON e.detailid = s.smsid "
                "WHERE e.eventtype = 'sms' "
                 f"AND eventdt > '{start}' "
                 f"AND e.userid = '{user_id}' "
                 f"AND (s.conversation = '{conversation}' "
                 f"OR (s.conversation IS NULL and s.contact_num = '{conversation}')) "
                 "ORDER BY eventdt ASC "
                 f"LIMIT {length}) s "
                 "ORDER BY s.eventdt DESC LIMIT 1")

    output = get_results_for_query(sms_query)

    return output


def insert_into_table_with_columns(data, table):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    # Right now this assumes all rows will have same columns
    db_columns = ", ".join(data[0].db_columns)

    all_rows = list()

    for row in data:
        values = list()

        for i in range(0, len(row.db_columns)):
            # expects fget to format all values correctly
            values.append(row.fget(row.db_columns[i]))

        row_values = "(" + ", ".join(values) + ")"

        all_rows.append(row_values)

    # Hardcoding groups of 500. Maybe someday make this customizable
    grouped_rows = group_insert_into_db(all_rows, 500)

    update_cols = list()

    for col in data[0].update_columns:
        update_cols_text = f"{col}=values({col})"
        update_cols.append(update_cols_text)

    update_columns = ", ".join(update_cols)

    for summary_rows in grouped_rows:
        sql = (f"INSERT INTO {table} ({db_columns}) "
               f"VALUES {summary_rows} "
               f"ON DUPLICATE KEY UPDATE {update_columns};")

        # TODO: Once these all work, remove this conditional
        cursor.execute(sql)

    cnx.commit()

    close_connection(cnx)

def get_trophies_that_updated(userid):

    query = f"""
    SELECT
    game_id,
    np_service_name,
    trophy_set_version
    FROM psn_summary
    WHERE
    userid = {userid}
    AND
    (last_updated > last_checked
    OR
    last_checked IS NULL)
    """

    output = get_results_for_query(query)

    return output

def update_trophies_last_checked(userid, service, set, game_id, time):

    cnx = create_connection("social")
    cursor = cnx.cursor()

    sql = f"""
    UPDATE psn_summary
    SET last_checked = "{time}"
    WHERE np_service_name = "{service}"
    AND userid = {userid}
    AND trophy_set_version = "{set}"
    AND game_id = "{game_id}"
    """

    cursor.execute(sql)

    cnx.commit()

    close_connection(cnx)


def close_connection(cnx):

    return cnx.close()
