from datetime import datetime, timedelta

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
        expense_date,
        is_recurring=0,
        recurring_frequency='monthly',
        tags='',
        currency='VND'
    ):

        query = """
            INSERT INTO expenses
            (
                user_id,
                amount,
                category,
                description,
                expense_date,
                is_recurring,
                recurring_frequency,
                tags,
                currency
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        return self.database.execute(
            query,
            (
                user_id,
                amount,
                category,
                description,
                expense_date,
                int(bool(is_recurring)),
                recurring_frequency or 'monthly',
                tags or '',
                currency or 'VND'
            )
        )

    # =========================
    # LẤY DANH SÁCH
    # =========================

    def get_expenses(self, user_id, start_date=None, end_date=None, category=None, keyword=None, tags=None, limit=None, offset=0):

        query = """
            SELECT
                id,
                user_id,
                amount,
                category,
                description,
                expense_date,
                is_recurring,
                recurring_frequency,
                tags,
                currency

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
        if tags:
            tag_value = str(tags).strip().lower()
            query += " AND LOWER(tags) LIKE ?"
            parameters.append(f"%{tag_value}%")
        query += " ORDER BY expense_date DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            parameters.extend([int(limit), int(offset)])

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
                row[5],
                row[6],
                row[7],
                row[8],
                row[9]
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
        expense_date,
        is_recurring=0,
        recurring_frequency='monthly',
        tags='',
        currency='VND'
    ):

        query = """
            UPDATE expenses

            SET
                amount = ?,
                category = ?,
                description = ?,
                expense_date = ?,
                is_recurring = ?,
                recurring_frequency = ?,
                tags = ?,
                currency = ?

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
                int(bool(is_recurring)),
                recurring_frequency or 'monthly',
                tags or '',
                currency or 'VND',
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

        existing = self.database.fetch_one(
            "SELECT id FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        if existing is None:
            return False

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
        current_month = datetime.now().strftime("%Y-%m")
        previous_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        current_total = self.total_by_month(user_id, current_month)
        previous_total = self.total_by_month(user_id, previous_month)
        change_percent = round(((current_total - previous_total) / previous_total) * 100, 1) if previous_total else None
        return {
            "transaction_count": totals[0],
            "total_amount": totals[1],
            "average_amount": round(totals[2], 2),
            "largest_amount": totals[3],
            "top_category": top_category[0] if top_category else "Chưa có dữ liệu",
            "top_category_amount": top_category[1] if top_category else 0,
            "current_month_total": current_total,
            "previous_month_total": previous_total,
            "month_change_percent": change_percent,
        }

    def upsert_category_budget(self, user_id, category, budget_amount, currency='VND'):
        category_value = str(category).strip()
        if not category_value:
            return False
        query = """
            INSERT INTO category_budgets (user_id, category, budget_amount, currency)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, category, currency)
            DO UPDATE SET budget_amount = excluded.budget_amount
        """
        return self.database.execute(query, (user_id, category_value, float(budget_amount), currency))

    def list_category_budgets(self, user_id):
        rows = self.database.fetch_all(
            "SELECT category, budget_amount, currency FROM category_budgets WHERE user_id = ? ORDER BY category ASC",
            (user_id,),
        )
        return [{"category": row[0], "budget_amount": row[1], "currency": row[2]} for row in rows]

    def get_user_setting(self, user_id):
        row = self.database.fetch_one(
            "SELECT default_currency, theme, refresh_token, last_backup_at FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        if row is None:
            return {"default_currency": "VND", "theme": "blue", "refresh_token": None, "last_backup_at": None}
        return {
            "default_currency": row[0] or "VND",
            "theme": row[1] or "blue",
            "refresh_token": row[2],
            "last_backup_at": row[3],
        }

    def save_user_setting(self, user_id, default_currency=None, theme=None, refresh_token=None):
        current = self.get_user_setting(user_id)
        if default_currency is None:
            default_currency = current["default_currency"]
        if theme is None:
            theme = current["theme"]
        if refresh_token is None:
            refresh_token = current["refresh_token"]
        existing = self.database.fetch_one("SELECT 1 FROM user_settings WHERE user_id = ?", (user_id,))
        if existing:
            return self.database.execute(
                "UPDATE user_settings SET default_currency = ?, theme = ?, refresh_token = ? WHERE user_id = ?",
                (default_currency, theme, refresh_token, user_id),
            )
        return self.database.execute(
            "INSERT INTO user_settings (user_id, default_currency, theme, refresh_token) VALUES (?, ?, ?, ?)",
            (user_id, default_currency, theme, refresh_token),
        )

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