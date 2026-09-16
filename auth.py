import hashlib

import bcrypt

from models import User


class AuthService:

    def __init__(self, database):
        self.database = database

    @staticmethod
    def hash_password(password):
        """Tạo bcrypt hash an toàn cho password."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password, password_hash):
        """Xác thực password với bcrypt hoặc legacy hash SHA256."""
        if not password_hash:
            return False
        if password_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash

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
        query = """
            SELECT id, username, password, role
            FROM users
            WHERE username = ?
        """

        user_data = self.database.fetch_one(query, (username,))
        if not user_data:
            return None

        stored_hash = user_data[2]
        if not self.verify_password(password, stored_hash):
            return None

        return User(
            user_data[0],
            user_data[1],
            user_data[2],
            user_data[3]
        )

    def change_password(self, user_id, current_password, new_password):
        if len(new_password) < 6:
            return False
        user_data = self.database.fetch_one(
            "SELECT password FROM users WHERE id = ?",
            (user_id,),
        )
        if not user_data or not self.verify_password(current_password, user_data[0]):
            return False
        new_hash = self.hash_password(new_password)
        return self.database.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (new_hash, user_id),
        )