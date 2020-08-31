import eventdb


class UserPreferences:
    def __init__(self, user_id):
        self.user_id = user_id
        db_prefs = eventdb.get_user_preferences(self.user_id)
        self.timezone = db_prefs.get('timezone') or 'UTC'
        self.reverse_order = int(db_prefs.get('reverse_order') or 0)

    def update(self, **kwargs):
        self.timezone = kwargs.get('timezone') or self.timezone
        self.reverse_order = kwargs.get('reverse_order')
        eventdb.set_user_preferences(1,
                                     timezone=self.timezone,
                                     reverse_order=self.reverse_order)

