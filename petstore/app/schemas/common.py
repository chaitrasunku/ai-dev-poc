from enum import Enum


class PetStatus(str, Enum):
    """Enum for possible pet statuses."""
    available = "available"
    pending = "pending"
    sold = "sold"


class OrderStatus(str, Enum):
    """Enum for possible order statuses."""
    placed = "placed"
    approved = "approved"
    delivered = "delivered"


class UserStatus(str, Enum):
    """Enum for possible user statuses."""
    active = "active"
    inactive = "inactive"
    banned = "banned"