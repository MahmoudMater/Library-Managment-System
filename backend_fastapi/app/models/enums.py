import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class BorrowStatus(str, enum.Enum):
    BORROWED = "borrowed"
    RETURNED = "returned"
    OVERDUE = "overdue"
