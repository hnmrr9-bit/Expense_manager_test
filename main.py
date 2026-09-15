import os

from database import Database
from auth import AuthService
from expense_service import ExpenseService
from file_service import FileService
from api_service import CurrencyAPI
from cli import CLI


def create_directories():

    os.makedirs(
        "data",
        exist_ok=True
    )

    os.makedirs(
        "exports",
        exist_ok=True
    )


def main():

    # Tạo thư mục cần thiết
    create_directories()

    # Khởi tạo Database
    database = Database()

    # Tạo các bảng nếu chưa tồn tại
    database.create_tables()

    # Khởi tạo các service
    auth_service = AuthService(
        database
    )

    expense_service = ExpenseService(
        database
    )

    file_service = FileService()

    currency_api = CurrencyAPI()

    # Khởi tạo giao diện CLI
    application = CLI(
        auth_service,
        expense_service,
        file_service,
        currency_api
    )

    # Chạy chương trình
    application.run()


if __name__ == "__main__":
    main()