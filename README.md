# Workout Bot

Workout Bot — Telegram-бот для планирования тренировок и персонального сопровождения. Он позволяет хранить базовые данные о пользователе, синхронизировать тренировки с сервисом [Gym-Stat](https://gym-stat.ru) и общаться с виртуальным тренером на базе ChatGPT или GigaChat.

## Возможности
- Регистрация и авторизация в Gym-Stat прямо из интерфейса бота.
- Два режима работы: локальное хранение данных и синхронизация с удалённым API.
- Ведение персональной анкеты (имя, возраст, вес, рост, пол) и просмотр профиля.
- Управление тренировками, упражнениями, группами упражнений, историей взвешиваний и параметрами тела.
- Пошаговые мастера (ConversationHandler) для создания и редактирования тренировочных записей.
- AI-консультант с выбором модели (ChatGPT или GigaChat), учитывающий персональные данные пользователя.
- Плановое удаление технических сообщений, чтобы поддерживать чистоту диалога.

## Требования
- Python 3.11 или выше (из-за зависимостей `python-telegram-bot==22.3` и `aiogram==3.22.0`).
- Установленные инструменты сборки Python (`python3-dev`, `build-essential`, `libffi-dev`, `libssl-dev`) — необходимы для сборки `cryptography`.
- Аккаунт Telegram с токеном бота от BotFather.
- (Опционально) Аккаунты и токены доступа для OpenAI и/или GigaChat, если планируется использовать AI-консультанта.

## Установка
1. Склонируйте репозиторий:  
   ```bash
   git clone <URL-репозитория> workout_bot
   cd workout_bot
   ```
2. Создайте виртуальное окружение:  
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```
3. Обновите базовые инструменты и установите зависимости:  
   ```bash
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

## Настройка окружения
Проект использует файл `.env`. Создайте его в корне репозитория, взяв за основу пример ниже.

| Переменная | Назначение | Обязательность | Примечания |
|------------|------------|----------------|------------|
| `TELEGRAM_TOKEN` | Токен Telegram-бота от BotFather. | Да | Используется `bot/config/settings.py`.
| `GYMSTAT_API_URL` | Базовый URL REST API Gym-Stat. | Нет | По умолчанию `https://api.gym-stat.ru`.
| `GYMSTAT_WEB_URL` | Базовый URL веб-версии Gym-Stat. | Нет | По умолчанию `https://gym-stat.ru`.
| `ENCRYPT_KEY` | Ключ Fernet для шифрования токенов. | Нет | Если не задан, генерируется при старте (но для устойчивости лучше задать вручную). |
| `OPENAI_API_KEY` | Ключ для ChatGPT. | Нет | Без него ChatGPT недоступен. |
| `OPENAI_API_URL` | Endpoint ChatGPT. | Нет | По умолчанию `https://api.openai.com/v1/chat/completions`. |
| `OPENAI_MODEL` | Идентификатор модели ChatGPT. | Нет | По умолчанию `gpt-4o-mini`. |
| `OAUTH_URL` | OAuth-endpoint GigaChat. | Для GigaChat | Выдаётся Сбером, например `https://ngw.devices.sberbank.ru:9443/api/v2/oauth`. |
| `CLIENT_CREDENTIALS` | Базовая авторизация для GigaChat (`base64(client_id:secret)`). | Для GigaChat | Требуется для получения токена. |
| `GIGACHAT_API_URL` | Endpoint GigaChat API. | Для GigaChat | Обычно `https://gigachat.devices.sberbank.ru/api/v1/chat/completions`. |

Пример `.env`:
```env
TELEGRAM_TOKEN=1234567890:ABCDEF...
GYMSTAT_API_URL=https://api.gym-stat.ru
GYMSTAT_WEB_URL=https://gym-stat.ru
ENCRYPT_KEY=<ваш-ключ-fernet>
OPENAI_API_KEY=sk-...
OAUTH_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
CLIENT_CREDENTIALS=base64(client_id:secret)
GIGACHAT_API_URL=https://gigachat.devices.sberbank.ru/api/v1/chat/completions
```

### Получение ключа Fernet
Если ключ не задан, `bot/config/settings.py` сгенерирует новый, но при перезапуске бота токены Gym-Stat станут недоступны. Чтобы создать ключ вручную:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Скопируйте результат в `ENCRYPT_KEY`.

## Инициализация базы данных
При первом запуске бот автоматически создаёт файл `bot/database/users.db` и таблицы `users` и `UserSettings`. Дополнительных миграций не требуется.

## Запуск
1. Убедитесь, что активировано виртуальное окружение и заполнен `.env`.
2. Запустите бота:  
   ```bash
   python -m bot.main
   ```
3. Добавьте бота в Telegram, отправьте команду `/start` и следуйте подсказкам.

### Работа в режиме Gym-Stat
1. Нажмите «🔄 Сменить режим» и выберите «Подключить Gym-Stat».
2. Используйте команды `/register` или `/login` для создания/входа в аккаунт Gym-Stat.
3. После успешной авторизации бот синхронизирует:
   - Список тренировок (с пагинацией и просмотром деталей).
   - Группы упражнений и упражнения (создание/редактирование/удаление).
   - Историю взвешиваний и обмеры тела.
4. Токены доступа шифруются с помощью `ENCRYPT_KEY` и обновляются автоматически за 5 минут до истечения срока действия.

### Работа с AI-консультантом
1. В главном меню нажмите «🤖 AI-консультант».
2. Выберите модель (ChatGPT или GigaChat). Если соответствующие ключи/креденшалы отсутствуют, бот сообщит об ошибке и предложит вернуться в меню.
3. Задавайте вопросы, бот будет учитывать сохранённые персональные данные. История ограничена 10 последними сообщениями, чтобы сохранять контекст, но не превышать лимиты API.
4. Для завершения консультации нажмите «🚪 Завершить консультацию» или команду `/cancel`.

## Логирование
- Конфигурация логгера находится в `bot/utils/logger.py`.
- По умолчанию все сообщения пишутся в стандартный вывод. Для перенаправления в файл используйте shell-редирект:  
  ```bash
  python -m bot.main >> logs/bot.log 2>&1
  ```
- Уровень логирования — INFO; предупреждения и ошибки записываются с дополнительными подробностями (HTTP-статусы, текст ответа API).

## Развёртывание на сервере
1. **Создайте системного пользователя** (например, `workoutbot`) без прав sudo.
2. **Скопируйте код** в `/opt/workout_bot` и выставьте владельца `workoutbot:workoutbot`.
3. **Настройте виртуальное окружение** внутри каталога (см. раздел «Установка»).
4. **Разместите файл `.env`** в `/opt/workout_bot/.env` с необходимыми секретами; ограничьте права (`chmod 600 .env`).
5. **Создайте `systemd`-юнит** `/etc/systemd/system/workout-bot.service`:
   ```ini
   [Unit]
   Description=Workout Bot Telegram service
   After=network.target

   [Service]
   Type=simple
   User=workoutbot
   Group=workoutbot
   WorkingDirectory=/opt/workout_bot
   Environment="PYTHONUNBUFFERED=1"
   EnvironmentFile=/opt/workout_bot/.env
   ExecStart=/opt/workout_bot/.venv/bin/python -m bot.main
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
6. Выполните `sudo systemctl daemon-reload`, затем `sudo systemctl enable --now workout-bot`.
7. Просматривайте журнал: `journalctl -u workout-bot -f`.

Для обновления версии достаточно выполнить `git pull`, `pip install -r requirements.txt` и перезапустить службу.

## Резервное копирование данных
- Основные данные находятся в файле SQLite `bot/database/users.db`.
- Для регулярного бэкапа остановите сервис, создайте копию файла и снова запустите бота.
- При необходимости переноса на другой сервер перенесите файл БД и `.env`.

## Обновление зависимостей
Для обновления зависимостей рекомендуется использовать `pip-tools` или `uv`, но минимальный сценарий:
```bash
pip install --upgrade -r requirements.txt
```
Перед деплоем убедитесь, что новая версия библиотек совместима с Telegram API и Gym-Stat.

## Тестирование
Автоматические тесты в репозитории отсутствуют. Рекомендуется вручную прогонять ключевые сценарии:
- `/start`, переключение режимов, заполнение анкеты.
- `/register` и `/login` в тестовом аккаунте Gym-Stat.
- Создание/редактирование/удаление тренировок, групп упражнений и записей веса.
- Диалог с AI-консультантом в обоих режимах (при наличии токенов).

## Диагностика и устранение неполадок
- **Отсутствует ответ бота в Telegram.** Проверьте, что процесс запущен и использует актуальный `TELEGRAM_TOKEN`.
- **Не удаётся войти в Gym-Stat.** Убедитесь, что API доступно, а `ENCRYPT_KEY` не менялся с момента сохранения токенов.
- **Ошибки GigaChat (401/500).** Проверьте срок действия OAuth-токена, корректность `CLIENT_CREDENTIALS` и доступность endpoint.
- **ChatGPT отвечает ошибкой 401/429.** Проверьте `OPENAI_API_KEY` и квоты в аккаунте OpenAI.
- **Сообщения в чате исчезают слишком быстро.** Измените задержку в `bot/utils/message_deletion.py` или временно отключите удаление.

## Структура проекта
Подробная техническая документация содержится в файле [AGENTS.md](./AGENTS.md). Рекомендуется ознакомиться с ним перед разработкой новых функций.
