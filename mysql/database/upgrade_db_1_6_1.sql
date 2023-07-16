USE social;

ALTER TABLE tweet_in_reply
MODIFY COLUMN statustext VARCHAR(380);