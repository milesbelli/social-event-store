# social-event-store

*What if all your personal data could be joined together in one single database?*

The goal of this project is relatively simple: create one database that contains the entirety of the user's online or otherwise digital presence. What you do with this after the database has been established is entirely up to you.

### What Works

Currently, a very rudimentary Twitter archive parser is included, along with a module for importing it into an existing database. The following tweet-related fields are populated:

* Tweet text
* User ID
* Geodata (if exists)
* Reply-to user ID (if exists)

The goal here will be to expand to as much metadata as possible.

Currently the only way to import tweets are through an archive, and at that, only the .js files within the library. The CSV file that accompanies Twitter archives is too limited and incomplete. The .js files exist in the archive more or less exactly how the data is stored on Twitter's website, although some data for older tweets can be missing or incomplete.

To import these files, they must all be located in the same directory and that directory must be specified when calling the `processDirectory` function. The `processDirectory` function will handle looping through all .js files and adding them to the MySQL database.

### What Doesn't

The project currently assumes the database and all tables have already been created. This is obviously a terrible thing to assume and one of the next steps will be to add some setup functions so that the database can be easily created.
