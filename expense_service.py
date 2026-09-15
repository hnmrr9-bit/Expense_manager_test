from models import Expense


class ExpenseService:

    def __init__(self, database):
        self.database = database

    # =========================
    # THÊM GIAO DỊCH
    # =========================

    def add_expense(
        self,
        user_id,
        amount,
        category,
        description,
        expense_date
    ):

        query = """
            INSERT INTO expenses
            (
                user_id,
                amount,
                category,
                description,
                expense_date
            )
            VALUES (?, ?, ?, ?, ?)
        """

        return self.database.execute(
            query,
            (
                user_id,
                amount,
                category,
                description,
                expense_date
            )
        )

    # =========================
    # LẤY DANH SÁCH
    # =========================

    def get_expenses(self, user_id, start_date=None, end_date=None, category=None, keyword=None):

        query = """
            SELECT
                id,
                user_id,
                amount,
                category,
                description,
                expense_date

            FROM expenses

            WHERE user_id = ?
        """

        parameters = [user_id]
        if start_date:
            query += " AND expense_date >= ?"
            parameters.append(start_date)
        if end_date:
            query += " AND expense_date <= ?"
            parameters.append(end_date)
        if category:
            query += " AND category = ?"
            parameters.append(category)
        if keyword:
            query += " AND (category LIKE ? OR description LIKE ?)"
            search_keyword = f"%{keyword}%"
            parameters.extend([search_keyword, search_keyword])
        query += " ORDER BY expense_date DESC"

        rows = self.database.fetch_all(
            query,
            tuple(parameters)
        )

        expenses = []

        for row in rows:

            expense = Expense(
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5]
            )

            expenses.append(expense)

        return expenses

    # =========================
    # SỬA GIAO DỊCH
    # =========================

    def update_expense(
        self,
        expense_id,
        user_id,
        amount,
        category,
        description,
        expense_date
    ):

        query = """
            UPDATE expenses

            SET
                amount = ?,
                category = ?,
                description = ?,
                expense_date = ?

            WHERE id = ?
            AND user_id = ?
        """

        return self.database.execute(
            query,
            (
                amount,
                category,
                description,
                expense_date,
                expense_id,
                user_id
            )
        )

    # =========================
    # XÓA GIAO DỊCH
    # =========================

    def delete_expense(
        self,
        expense_id,
        user_id
    ):

        query = """
            DELETE FROM expenses

            WHERE id = ?
            AND user_id = ?
        """

        return self.database.execute(
            query,
            (
                expense_id,
                user_id
            )
        )

    # =========================
    # TỔNG CHI TIÊU
    # =========================

    def total_expense(self, user_id):

        query = """
            SELECT SUM(amount)

            FROM expenses

            WHERE user_id = ?
        """

        result = self.database.fetch_one(
            query,
            (user_id,)
        )

        if result is None or result[0] is None:

            return 0

        return result[0]

    # =========================
    # TỔNG THEO THÁNG
    # =========================

    def total_by_month(
        self,
        user_id,
        month
    ):

        query = """
            SELECT SUM(amount)

            FROM expenses

            WHERE user_id = ?

            AND substr(expense_date, 1, 7) = ?
        """

        result = self.database.fetch_one(
            query,
            (
                user_id,
                month
            )
        )

        if result is None or result[0] is None:

            return 0

        return result[0]

    # =========================
    # THỐNG KÊ THEO DANH MỤC
    # =========================

    def total_by_category(
        self,
        user_id
    ):

        query = """
            SELECT
                category,
                SUM(amount)

            FROM expenses

            WHERE user_id = ?

            GROUP BY category
        """

        rows = self.database.fetch_all(
            query,
            (user_id,)
        )

        result = {}

        for row in rows:

            category = row[0]
            total = row[1]

            result[category] = total

        return result

    def totals_by_month(self, user_id, year=None):
        query = """
            SELECT substr(expense_date, 1, 7), SUM(amount)
            FROM expenses WHERE user_id = ?
        """
        parameters = [user_id]
        if year:
            query += " AND substr(expense_date, 1, 4) = ?"
            parameters.append(str(year))
        query += " GROUP BY substr(expense_date, 1, 7) ORDER BY 1"
        return dict(self.database.fetch_all(query, tuple(parameters)))

    def totals_by_year(self, user_id):
        rows = self.database.fetch_all(
            "SELECT substr(expense_date, 1, 4), SUM(amount) FROM expenses WHERE user_id = ? GROUP BY 1 ORDER BY 1",
            (user_id,),
        )
        return dict(rows)

    def report(self, user_id):
        totals = self.database.fetch_one(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(AVG(amount), 0), COALESCE(MAX(amount), 0) FROM expenses WHERE user_id = ?",
            (user_id,),
        )
        top_category = self.database.fetch_one(
            "SELECT category, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        )
        return {
            "transaction_count": totals[0],
            "total_amount": totals[1],
            "average_amount": round(totals[2], 2),
            "largest_amount": totals[3],
            "top_category": top_category[0] if top_category else "Chưa có dữ liệu",
            "top_category_amount": top_category[1] if top_category else 0,
        }

    # =========================
    # TÌM KIẾM
    # =========================

    def search_expenses(
        self,
        user_id,
        keyword
    ):

        query = """
            SELECT
                id,
                user_id,
                amount,
                category,
                description,
                expense_date

            FROM expenses

            WHERE user_id = ?

            AND (
                category LIKE ?
                OR description LIKE ?
            )

            ORDER BY expense_date DESC
        """

        search_keyword = f"%{keyword}%"

        rows = self.database.fetch_all(
            query,
            (
                user_id,
                search_keyword,
                search_keyword
            )
        )

        expenses = []

        for row in rows:

            expenses.append(
                Expense(
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5]
                )
            )

        return expenses