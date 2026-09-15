import sqlite3


class Database:

    def __init__(self, database_name="data/expense.db"):
        self.database_name = database_name

    def connect(self):
        return sqlite3.connect(self.database_name)

    def create_tables(self):

        connection = self.connect()
        cursor = connection.cursor()

        # Tạo bảng người dùng
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
        """)

        # Tạo bảng giao dịch
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                expense_date TEXT NOT NULL,

                FOREIGN KEY (user_id)
                REFERENCES users(id)
            )
        """)

        user_columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
        if "role" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

        connection.commit()
        connection.close()

    def execute(self, query, parameters=()):

        connection = self.connect()
        cursor = connection.cursor()

        try:
            cursor.execute(query, parameters)

            connection.commit()

            return True

        except sqlite3.Error as error:

            connection.rollback()

            print(f"Lỗi database: {error}")

            return False

        finally:

            connection.close()

    def fetch_all(self, query, parameters=()):

        connection = self.connect()
        cursor = connection.cursor()

        try:

            cursor.execute(query, parameters)

            return cursor.fetchall()

        except sqlite3.Error as error:

            print(f"Lỗi database: {error}")

            return []

        finally:

            connection.close()

    def fetch_one(self, query, parameters=()):

        connection = self.connect()
        cursor = connection.cursor()

        try:

            cursor.execute(query, parameters)

            return cursor.fetchone()

        except sqlite3.Error as error:

            print(f"Lỗi database: {error}")

            return None

        finally:

            connection.close()