class Store:
    """Основной класс хранилища для управления доступом к данным.

    Предоставляет единый доступ к различным аксессорам данных.
    """

    def __init__(self, *args, **kwargs):
        """Инициализирует хранилище с необходимыми аксессорами.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        from app.users.accessor import UserAccessor

        self.user = UserAccessor(self)
