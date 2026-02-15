class Futures:
    def __init__(self, underlying_price, cost_of_carry, time_to_expiry):
        self.underlying_price = underlying_price
        self.cost_of_carry = cost_of_carry
        self.time_to_expiry = time_to_expiry

    def calculate_futures_price(self):
        pass

    def simulate_pnl(self, entry_price, current_price):
        pass

    def check_contango_backwardation(self):
        pass

    def display_dashboard(self):
        pass
