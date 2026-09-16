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
        expense_date,
        is_recurring=0,
        recurring_frequency='monthly',
        tags='',
        currency='VND'
    ):
        self.expense_id = expense_id
        self.user_id = user_id
        self.amount = amount
        self.category = category
        self.description = description
        self.expense_date = expense_date
        self.is_recurring = bool(is_recurring)
        self.recurring_frequency = recurring_frequency or 'monthly'
        self.tags = tags or ''
        self.currency = currency or 'VND'

    def to_dict(self):
        """Chuyển đối tượng Expense thành Dictionary."""

        return {
            "id": self.expense_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "category": self.category,
            "description": self.description,
            "date": self.expense_date,
            "is_recurring": self.is_recurring,
            "recurring_frequency": self.recurring_frequency,
            "tags": self.tags,
            "currency": self.currency,
        }