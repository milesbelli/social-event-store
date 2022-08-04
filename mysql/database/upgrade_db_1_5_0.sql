USE social;

ALTER TABLE events
ADD COLUMN eventdt DATETIME
AFTER eventtime;

UPDATE events SET eventdt = CONCAT(eventdate,' ',eventtime);

ALTER TABLE events
MODIFY COLUMN eventdt DATETIME NOT NULL
AFTER eventtime;

CREATE INDEX EVENTS_IDX1
ON events (eventdt, eventtype);
