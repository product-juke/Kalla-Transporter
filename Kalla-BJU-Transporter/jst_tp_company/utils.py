# company_portfolio_visibility/utils.py
from functools import wraps
from odoo.exceptions import UserError

def only_for_portfolio(*allowed_portfolios, raise_error=False):
    """
    Decorator to run a method only if current company matches allowed portfolio(s).
    :param raise_error: If True, raise UserError. Else, silently skip method.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            company_portfolio = self.env.company.portfolio
            if company_portfolio in allowed_portfolios:
                return func(self, *args, **kwargs)
            if raise_error:
                raise UserError(f"Only available for portfolio(s): {', '.join(allowed_portfolios)}")
            return None
        return wrapper
    return decorator

# Shortcut decorators
transporter = only_for_portfolio('transporter')
trucking = only_for_portfolio('trucking')
retail = only_for_portfolio('retail')

# Optional: strict version that raises error
transporter_strict = only_for_portfolio('transporter', raise_error=True)
trucking_strict = only_for_portfolio('trucking', raise_error=True)
