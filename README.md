# social-event-store

The goal of this project is to bring data archives from disparate sources together in a single, unified database. Sorting through all your data should be a seamless, painless experience. While it is called Social Event Store, the concept applies equally well to any digital archive containing timestamped personal data.

## Sources

### Supported

* Twitter
* Fitbit Sleep

### Planned

* Instagram
* Mastodon
* Swarm/Foursquare
* SMS/text messages
* Last.fm scrobbles (via API)
* Steam achievements (via API)
* Mint transactions
* Peach???
* Facebook if I have to

## Roadmap

### Milestone 1 - Completed

* Read Twitter archive formats
* Import Twitter into database

### Milestone 2 - Completed

* Support reimporting (continuous updating)
* Export Twitter archive to *.ical file

### Milestone 3 - Completed

* Simple web viewer interface built on Flask

### Milestone 4 - Completed

* Read Fitbit archive format for sleep
* Import Fitbit sleep into database

### Milestone 5 - Completed

* Read Foursquare/Swarm archive format
* Import Swarm checkins into database

### Milestone 6 - In progress

* Preparing backend for multiple user logins
* User login
* Experimental SMS support

## Setup

*Requires Python 3 and pip installed, and requires MySQL running with root access*

1. In a terminal navigate to the social-event-store directory
2. In `create_database.sql`, change `socialuser` and `resetme` to be username and password of your choosing (or leave as default)
2. Log into MySQL as admin/root
3. Run the following command: 

    ```shell script
    source create_database.sql
    ```
4. Confirm queries execute OK
5. Exit out of MySQL
6. In the social-event-store directory, edit the file, `secure.py`
7. Change username and password to be whatever was set in `create_database.sql`
8. Host should be the IP address of your MySQL DB (if running locally, it'll be 127.0.0.1 or localhost)
9. It is recommended that you create a virtual environment for installing the required packages. Follow directions for creating one according to your OS.
10. Once running your virtual environment, while inside the `social-event-store/social` directory you can run:

    ```shell script
    pip install -r requirements.txt
    ```
11. After installing, you'll navigate to the `app` directory and run `web.py`.

    ```shell script
    cd app
    python web.py
    ```
12. At this point in time you should be running the Flask dev server and should be able to point your browser to `localhost:5000`.
13. You should see the web UI. Use the links to navigate to different features.

## Adding Data

*Currently only Twitter archives, Fitbit sleep archives, and Foursquare checkin archives are supported*

1. With the web UI running, click on `Upload` or point your address bar to `http://localhost:5000/upload`
2. Choose Twitter, Fitbit Sleep, or Foursquare from the dropdown and then select the zip file you wish to load into the system.
3. Click the upload button and begin the process.

Some warnings:
1. The file you upload MUST be a zip file.
2. Because files must be uploaded, it can be slow if you upload the entire archive as provided by the site. For that reason, it's recommended that files such as images be removed from the zip prior to uploading.
3. Before uploading Fitbit sleep data, it is *strongly recommended* that you set your local timezone under `http://localhost:5000/settings`. This is because Fitbit does NOT store timezone information and so this app will store the sleep data based on your local timezone. There is an edit feature to manually change individual sleep sessions to other timezones.
4. Foursquare checkin history is unfortunately limited. After uploading a Foursquare checkin archive, your events will appear in the UI with a footer that reads *Location unknown*. This is normal. Geolocation data for the venues visited is not stored with your checkin data. It must be downloaded from Foursquare's servers. To trigger this download, you must click the Map button on each individual checkin (once per venue). After doing this, geolocation data will be stored and you will see the "true" location in the footer.

## Exporting iCal

The other "half" of this project is to export the data back out again in an iCal file. This can be loaded into most calendar apps.

1. Navigate to the `Export` feature in the web UI.
2. Choose the type of data you'd like to export.
3. Choose a valid date range.
4. Click export. The page may hang while waiting for the export to complete.
5. Once the export is complete, a download link will appear beneath the menu. Click this link to download the file.
6. Open the file using Outlook or upload it to a web service like Google Calendar to view the events.