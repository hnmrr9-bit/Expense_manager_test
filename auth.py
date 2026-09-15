import hashlib

from models import User


class AuthService:

    def __init__(self, database):
        self.database = database

    def hash_password(self, password):
        """
        Chuyển password thành chuỗi hash
        trước khi lưu vào database.
        """

        return hashlib.sha256(
            password.encode("utf-8")
        ).hexdigest()

    def register(self, username, password):

        if len(username) < 3:

            print("Username phải có ít nhất 3 ký tự.")

            return False

        if len(password) < 6:

            print("Password phải có ít nhất 6 ký tự.")

            return False

        hashed_password = self.hash_password(password)

        query = """
            INSERT INTO users(username, password)
            VALUES (?, ?)
        """

        try:

            success = self.database.execute(
                query,
                (username, hashed_password)
            )

            if success:

                print("Đăng ký thành công!")

                return True

            return False

        except Exception as error:

            print(f"Lỗi đăng ký: {error}")

            return False

    def login(self, username, password):

        hashed_password = self.hash_password(password)

        query = """
            SELECT id, username, password, role
            FROM users
            WHERE username = ?
            AND password = ?
        """

        user_data = self.database.fetch_one(
            query,
            (username, hashed_password)
        )

        if user_data:

            return User(
                user_data[0],
                user_data[1],
                user_data[2],
                user_data[3]
            )

        return None