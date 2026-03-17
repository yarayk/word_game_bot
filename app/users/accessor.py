class UserAccessor:
    """Аксессор для работы с данными пользователей.

    Attributes:
    ----------
    config : dict
        конфигурация класса UserAccessor
    """

    def __init__(self, config) -> None:
        """Инициализирует класс UserAccessor.

        Parameters
        ----------
        config : dict
            конфигурация класса UserAccessor.
        """
        self.config = config
