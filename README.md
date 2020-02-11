# social-event-store

The goal of this project is to bring data archives from disparate sources together in a single, unified database. Sorting through all your data should be a seamless, painless experience. While it is called Social Event Store, the concept applies equally well to any digital archive containing timestamped personal data.

## Sources

### In Progress

* Twitter

### Planned

* Fitbit
* Instagram
* Mastodon
* Swarm/Foursquare
* SMS/text messages
* Peach???
* Facebook if I have to

## Roadmap

### Milestone 1 - Current

* Read Twitter archive formats
* Import Twitter into database

### Milestone 2

* Support reimporting (continuous updating)
* Export Twitter archive to *.ical file

### Milestone 3

* Simple web viewer interface built on Flask

### Milestone 4

* Read Fitbit archive format for sleep
* Read Fitbit archive format for exercise
* Import Fitbit sleep and exercise into database

*Future milestones TBA*

### Setup

*Requires Python 3 installed, and requires MySQL running with root access*

1. In a terminal navigate to the social-event-store directory
2. In `create_database.sql`, change `socialuser` and `resetme` to be username and password of your choosing (or leave as default)
2. Log into MySQL as admin/root
3. Run the following command: 

    ```shell script
    source create_database.sql
    ```
4. Confirm queries execute OK
5. Exit out of MySQL
6. In the social-event-store directory, create a file, `secure.py`
7. File should look like:
```python
def username():
    return 'socialuser'

def password():
    return 'resetme'
```
8. Change username and password to be whatever was set in `create_database.sql`
9. For Twitter, in `twitter.py` set the directory of tweet js files, call function `processDirectory()` with the directory path
