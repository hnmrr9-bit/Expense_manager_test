class User:
    def __init__(self, user_id, username, password, role="user"):
        self.user_id = user_id
        self.username = username
        self.password = password
        self.role = role


class Expense:
    def __init__(
        self,
        expense_id,
        user_id,
        amount,
        category,
        description,
        expense_date
    ):
        self.expense_id = expense_id
        self.user_id = user_id
        self.amount = amount
        self.category = category
        self.description = description
        self.expense_date = expense_date

    def to_dict(self):
        """
        Chuyển đối tượng Expense thành Dictionary.
        Dictionary sẽ được dùng khi export dữ liệu sang JSON.
        """

        return {
            "id": self.expense_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "category": self.category,
            "description": self.description,
            "date": self.expense_date
        }