from datetime import datetime


class CLI:

    def __init__(
        self,
        auth_service,
        expense_service,
        file_service,
        currency_api
    ):

        self.auth = auth_service

        self.expense_service = expense_service

        self.file_service = file_service

        self.currency_api = currency_api

        self.current_user = None

    # =========================
    # CHƯƠNG TRÌNH
    # =========================

    def run(self):

        while True:

            self.show_header()

            print("1. Đăng ký")
            print("2. Đăng nhập")
            print("0. Thoát")

            choice = input("Chọn: ")

            if choice == "1":

                self.register()

            elif choice == "2":

                if self.login():

                    self.main_menu()

            elif choice == "0":

                print("Tạm biệt!")

                break

            else:

                print("Lựa chọn không hợp lệ.")

    # =========================
    # HEADER
    # =========================

    def show_header(self):

        print()
        print("=" * 40)
        print("      QUẢN LÝ CHI TIÊU PYTHON")
        print("=" * 40)

    # =========================
    # ĐĂNG KÝ
    # =========================

    def register(self):

        username = input(
            "Username: "
        ).strip()

        password = input(
            "Password: "
        ).strip()

        self.auth.register(
            username,
            password
        )

    # =========================
    # ĐĂNG NHẬP
    # =========================

    def login(self):

        username = input(
            "Username: "
        ).strip()

        password = input(
            "Password: "
        ).strip()

        user = self.auth.login(
            username,
            password
        )

        if user:

            self.current_user = user

            print(
                f"\nXin chào {user.username}!"
            )

            return True

        print(
            "\nSai username hoặc password."
        )

        return False

    # =========================
    # MENU CHÍNH
    # =========================

    def main_menu(self):

        while True:

            print()
            print("=" * 40)
            print("           MENU CHI TIÊU")
            print("=" * 40)

            print("1. Thêm giao dịch")
            print("2. Xem giao dịch")
            print("3. Sửa giao dịch")
            print("4. Xóa giao dịch")
            print("5. Tìm kiếm")
            print("6. Tổng chi tiêu")
            print("7. Tổng theo tháng")
            print("8. Thống kê danh mục")
            print("9. Export JSON")
            print("10. Đổi tiền bằng API")
            print("0. Đăng xuất")

            choice = input(
                "Chọn: "
            ).strip()

            if choice == "1":

                self.add_expense()

            elif choice == "2":

                self.show_expenses()

            elif choice == "3":

                self.update_expense()

            elif choice == "4":

                self.delete_expense()

            elif choice == "5":

                self.search_expenses()

            elif choice == "6":

                self.show_total()

            elif choice == "7":

                self.show_month_total()

            elif choice == "8":

                self.show_category_total()

            elif choice == "9":

                self.export_data()

            elif choice == "10":

                self.currency_convert()

            elif choice == "0":

                self.current_user = None

                print("Đã đăng xuất.")

                break

            else:

                print(
                    "Lựa chọn không hợp lệ."
                )

    # =========================
    # THÊM GIAO DỊCH
    # =========================

    def add_expense(self):

        try:

            amount = float(
                input("Số tiền: ")
            )

            if amount <= 0:

                print(
                    "Số tiền phải lớn hơn 0."
                )

                return

            category = input(
                "Danh mục: "
            ).strip()

            description = input(
                "Mô tả: "
            ).strip()

            expense_date = input(
                "Ngày YYYY-MM-DD: "
            ).strip()

            datetime.strptime(
                expense_date,
                "%Y-%m-%d"
            )

            success = (
                self.expense_service.add_expense(
                    self.current_user.user_id,
                    amount,
                    category,
                    description,
                    expense_date
                )
            )

            if success:

                print(
                    "Thêm giao dịch thành công."
                )

            else:

                print(
                    "Không thể thêm giao dịch."
                )

        except ValueError:

            print(
                "Dữ liệu nhập không hợp lệ."
            )

    # =========================
    # HIỂN THỊ
    # =========================

    def show_expenses(
        self,
        expenses=None
    ):

        if expenses is None:

            expenses = (
                self.expense_service.get_expenses(
                    self.current_user.user_id
                )
            )

        if not expenses:

            print(
                "\nChưa có giao dịch."
            )

            return

        print()
        print("-" * 80)

        for expense in expenses:

            print(
                f"ID: {expense.expense_id} | "
                f"{expense.expense_date} | "
                f"{expense.category} | "
                f"{expense.amount:,.0f} VNĐ | "
                f"{expense.description}"
            )

        print("-" * 80)

    # =========================
    # SỬA
    # =========================

    def update_expense(self):

        try:

            expense_id = int(
                input("ID cần sửa: ")
            )

            amount = float(
                input("Số tiền mới: ")
            )

            category = input(
                "Danh mục mới: "
            ).strip()

            description = input(
                "Mô tả mới: "
            ).strip()

            expense_date = input(
                "Ngày mới YYYY-MM-DD: "
            ).strip()

            datetime.strptime(
                expense_date,
                "%Y-%m-%d"
            )

            success = (
                self.expense_service.update_expense(
                    expense_id,
                    self.current_user.user_id,
                    amount,
                    category,
                    description,
                    expense_date
                )
            )

            if success:

                print(
                    "Đã cập nhật giao dịch."
                )

            else:

                print(
                    "Không thể cập nhật."
                )

        except ValueError:

            print(
                "Dữ liệu không hợp lệ."
            )

    # =========================
    # XÓA
    # =========================

    def delete_expense(self):

        try:

            expense_id = int(
                input("ID cần xóa: ")
            )

            confirm = input(
                "Bạn chắc chắn muốn xóa? (y/n): "
            ).lower()

            if confirm == "y":

                success = (
                    self.expense_service.delete_expense(
                        expense_id,
                        self.current_user.user_id
                    )
                )

                if success:

                    print(
                        "Đã xóa giao dịch."
                    )

                else:

                    print(
                        "Không thể xóa giao dịch."
                    )

            else:

                print("Đã hủy.")

        except ValueError:

            print(
                "ID phải là số."
            )

    # =========================
    # TÌM KIẾM
    # =========================

    def search_expenses(self):

        keyword = input(
            "Nhập từ khóa: "
        ).strip()

        expenses = (
            self.expense_service.search_expenses(
                self.current_user.user_id,
                keyword
            )
        )

        self.show_expenses(expenses)

    # =========================
    # TỔNG
    # =========================

    def show_total(self):

        total = (
            self.expense_service.total_expense(
                self.current_user.user_id
            )
        )

        print(
            f"\nTổng chi tiêu: "
            f"{total:,.0f} VNĐ"
        )

    # =========================
    # THEO THÁNG
    # =========================

    def show_month_total(self):

        month = input(
            "Nhập tháng YYYY-MM: "
        ).strip()

        try:

            datetime.strptime(
                month,
                "%Y-%m"
            )

            total = (
                self.expense_service.total_by_month(
                    self.current_user.user_id,
                    month
                )
            )

            print(
                f"Chi tiêu tháng {month}: "
                f"{total:,.0f} VNĐ"
            )

        except ValueError:

            print(
                "Định dạng phải là YYYY-MM."
            )

    # =========================
    # THỐNG KÊ DANH MỤC
    # =========================

    def show_category_total(self):

        result = (
            self.expense_service.total_by_category(
                self.current_user.user_id
            )
        )

        if not result:

            print(
                "Chưa có dữ liệu."
            )

            return

        print("\nTHỐNG KÊ")

        for category, total in result.items():

            print(
                f"{category}: "
                f"{total:,.0f} VNĐ"
            )

    # =========================
    # EXPORT
    # =========================

    def export_data(self):

        expenses = (
            self.expense_service.get_expenses(
                self.current_user.user_id
            )
        )

        self.file_service.export_expenses(
            expenses,
            "exports/expenses.json"
        )

    # =========================
    # API
    # =========================

    def currency_convert(self):

        try:

            amount = float(
                input("Số tiền: ")
            )

            base = input(
                "Tiền gốc (VD USD): "
            ).strip()

            target = input(
                "Tiền đích (VD EUR): "
            ).strip()

            result = (
                self.currency_api.convert(
                    amount,
                    base,
                    target
                )
            )

            if result is not None:

                print(
                    f"\n{amount} "
                    f"{base.upper()} = "
                    f"{result:,.2f} "
                    f"{target.upper()}"
                )

        except ValueError:

            print(
                "Số tiền không hợp lệ."
            )