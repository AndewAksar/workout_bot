import sqlite3


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS UserSettings
                 (user_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, weight REAL, height REAL, training_type TEXT)''')
    conn.commit()
    conn.close()