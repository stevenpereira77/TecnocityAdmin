class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class InsufficientStockError(DomainError):
    pass
