class Store:
    def __init__(self, *args, **kwargs):
        from app.users.accessor import UserAccessor

        self.user = UserAccessor(self)
