# bot/utils/logger.py
"""
Модуль: logger.py
Описание: Модуль для настройки и использования логгера с поддержкой файлов и консоли.
Этот модуль предоставляет функцию `setup_logging`, которая создаёт и настраивает
логгер с возможностью записи в файл (с ротацией) и вывода в консоль.

Зависимости:
- os: для работы с файловой системой.
- logging: для работы с логгированием.
- logging.handlers: для поддержки ротации файлов.

Автор: Aksarin A.
Дата создания: 21/08/2025
"""

import logging
import os
from logging.handlers import RotatingFileHandler


# Конфигурационные константы
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
"""Формат строки лога для записи в файл."""

CONSOLE_LOG_FORMAT = '%(levelname)s: %(message)s'
"""Формат строки лога для вывода в консоль."""

DEFAULT_LOG_LEVEL = logging.INFO
"""Уровень логирования по умолчанию."""

FILE_LOG_LEVEL = logging.DEBUG
"""Уровень логирования для файла."""

CONSOLE_LOG_LEVEL = logging.DEBUG
"""Уровень логирования для консоли."""

DEFAULT_LOG_FILE = os.path.join("logs", "test_bot.log")
"""Путь к файлу логов по умолчанию."""

def setup_logging(
        log_file: str = DEFAULT_LOG_FILE,
        logger_name: str = __name__,
        max_bytes: int = 10*1024*1024,
        backup_count: int = 5,
        log_level: str = os.getenv("LOG_LEVEL", "INFO")
) -> logging.Logger:
    """
    Инициализирует и настраивает логгер с поддержкой файла и консоли.

    Создаёт экземпляр логгера, который может писать сообщения как в файл,
    так и в консоль. Если файл логов недоступен (например, из-за прав),
    то логирование будет происходить только в консоль.

    Аргументы:
        log_file (str): Путь к файлу логов. По умолчанию - ``logs/test_bot.log``.
        logger_name (str): Имя логгера. По умолчанию - имя текущего модуля.
        max_bytes (int): Максимальный размер файла логов перед ротацией (в байтах).
                         По умолчанию — 10 МБ.
        backup_count (int): Количество резервных файлов логов при ротации.
                            По умолчанию — 5.
        log_level (str): Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                         Может быть переопределён через переменную окружения LOG_LEVEL.
                         По умолчанию — INFO.
    Возвращаемое значение:
        logging.Logger: Настроенный экземпляр логгера.

    Пример использования:
        >>> logger = setup_logging()
        >>> logger.info("Привет, мир!")
    """
    # Получаем или создаём логгер по имени
    logger = logging.getLogger(logger_name)

    # Проверяем, был ли уже инициализирован логгер
    if logger.hasHandlers():
        logger.debug(f"Логгер уже инициализирован. Пропускаем инициализацию.")
        return logger

    # Устанавливаем уровень логирования
    level = getattr(logging, log_level.upper(), DEFAULT_LOG_LEVEL)
    logger.setLevel(level)

    # Создаём директорию для логов, если её нет
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Определяем форматтеры
    file_formatter = logging.Formatter(LOG_FORMAT)
    console_formatter = logging.Formatter(CONSOLE_LOG_FORMAT)

    # Настраиваем обработчик для записи в файл с ротацией
    file_handler = None
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
    except PermissionError as e:
        logger.warning(
            f"Ошибка доступа к файлу логов {log_file}: {e}. "
            f"Логи будут записываться только в консоль."
        )

    # Добавляем файловый обработчик, если он создан успешно
    if file_handler:
        file_handler.setLevel(FILE_LOG_LEVEL)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Настраиваем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(CONSOLE_LOG_LEVEL)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Логируем успешную инициализацию
    logger.debug(f"Логгер инициализирован, файл логов: {os.path.abspath(log_file)}")

    return logger