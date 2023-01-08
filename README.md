# social-event-store

The goal of this project is to bring data archives from disparate sources together in a single, unified database. Sorting through all your data should be a seamless, painless experience. While it is called Social Event Store, the concept applies equally well to any digital archive containing timestamped personal data.

## Sources

### Supported

* Twitter
* Fitbit Sleep
* Foursquare
* SMS/text messages

### Planned

* Instagram
* Mastodon
* Swarm/Foursquare
* Last.fm scrobbles (via API)
* Steam achievements (via API)
* Mint transactions
* Peach???
* Facebook if I have to
* PSN Trophies (via API)

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

### Milestone 6 - Completed

* Preparing backend for multiple user logins
* Experimental SMS support
* Docker integration for production

### Milestone 7 - In Progress

* User login
* Import trophy data from unofficial PSN API
* Import archive files from Mastodon

## Setup

There are two ways to set up this program to run locally on your computer. You can either follow the instructions for local development and testing to run the actual Python code (requires a bunch of stuff to be installed and configured), or you can follow the instructions for Docker setup (which just requires Docker* to be installed).

*If running on Windows 10 or higher, you should also have WSL2 installed

### For Local Development or Testing

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
6. You will need to set up some environment variables to whatever was set in `create_database.sql`:

    ```
    DB_HOST=social_mysql
    DB_USER=socialuser
    DB_PASS=resetme
    ```

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

### Using Docker

1. Install [Docker](https://www.docker.com/get-started), following the instructions for whatever OS you're using
2. If on Windows 10, I recommend following [these setup instructions](https://docs.docker.com/desktop/windows/wsl/) to configure WSL2 (the containers might run without it but I've not tried and can't guarantee the results)
3. Download the latest source code and extract it somewhere
4. Open a command prompt and navigate to that directory using a command like this (on Windows):

    ```
    cd "C:/path/to/that/directory/"
    ```

5. Make sure you are in the directory where the file `prod.docker-compose.yml` is located
6. Run the below command

    ```
    docker-compose -f prod.docker-compose.yml up -d
    ```

7. It will download the containers and launch them. Once complete, you may need to wait a few moments for the containers to fully start (the database takes a minute to run its setup the first time)
8. Point your browser to [http://localhost](http://localhost) to test to see if the application is now running

## Adding Data

*Currently supported: Twitter archives, Fitbit sleep archives, and Foursquare check-in archives*

*SMS archives can be imported if you first run them through a converter to make them JSON, and several different kinds of importer scripts are included, but there is no guarantee those will work correctly*

*PSN Trophies can be pulled using the API; this requires you be logged in and following steps provided*

*For these instructions, if you're running via Docker, ignore the :5000 in the URLs*

### Archive files

1. With the web UI running, click on **Upload** or point your address bar to `http://localhost:5000/upload`
2. Choose Twitter, Fitbit Sleep, Foursquare, or SMS from the dropdown and then select the zip file you wish to load into the system.
3. Click the upload button and begin the process.

Some warnings:
1. The file you upload MUST be a zip file.
2. Because files must be uploaded, it can be slow if you upload the entire archive as provided by the site. For that reason, it's recommended that files such as images be removed from the zip prior to uploading.
3. Before uploading Fitbit sleep data, it is *strongly recommended* that you set your local timezone under `http://localhost:5000/settings`. This is because Fitbit does NOT store timezone information and so this app will store the sleep data based on your local timezone. There is an edit feature to manually change individual sleep sessions to other timezones.
4. Foursquare checkin history is unfortunately limited. After uploading a Foursquare checkin archive, your events will appear in the UI with a footer that reads *Location unknown*. This is normal. Geolocation data for the venues visited is not stored with your checkin data. It must be downloaded from Foursquare's servers. To trigger this download, you must click the Map button on each individual checkin (once per venue). After doing this, geolocation data will be stored and you will see the "true" location in the footer.
5. SMS archives are very much a DIY process. If you've downloaded the source code, you'll find the converter scripts in the following directory:

    ```
    /social/app/preprocessors/sms
    ```
    If you are using an archive from an Android phone, the script named `android_backup_xml.py` will probably work for you. Within that directory there should be an `input` directory. Place the archive file there. Run the script from inside its directory and an output should appear in the output directory. Zip that file up and it should be ready to upload to the app. I might include more detailed instructions on how to do this in the future.

### Pulling from PSN API

1. From the **Upload** page, click the API link or go directly to `http://localhost:5000/fetch`
2. Follow the instructions on the page
3. Once you click the **Fetch** button, the application will begin to fetch trophies

Warnings:

1. Use this at your own risk; the PSN API is not supported and could become unavailable at any moment
2. When using this function, your account could get locked, especially if entering an invalid or expired token
3. As of this version, there is no way to track API sync progress, or even know if it has failed. That will be added eventually.
4. If you have a lot of games on your account (150+) you might run into the maximum requests per limit when running the first time. If that happens, wait 15 minutes and try again.

*Special thanks to @andshrew for creating and maintaining [this documentation](https://andshrew.github.io/PlayStation-Trophies/#/APIv2) which details the PSN API. This functionality would not have been possible without it!*

## Exporting iCal

The other "half" of this project is to export the data back out again in an iCal file. This can be loaded into most calendar apps.

1. Navigate to the `Export` feature in the web UI.
2. Choose the type of data you'd like to export.
3. Choose a valid date range.
4. Click export. The page may hang while waiting for the export to complete.
5. Once the export is complete, a download link will appear beneath the menu. Click this link to download the file.
6. Open the file using Outlook or upload it to a web service like Google Calendar to view the events.
