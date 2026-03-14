import os


def read_version() -> str:
    """Читает версию из файла VERSION.

    Returns:
        str: Строка версии из файла VERSION.
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(current_dir, "..", "VERSION")) as f:
        return f.read().strip()


__appname__ = "kts_backend"
__version__ = read_version()
