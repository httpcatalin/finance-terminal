class Bond:
    def __init__(self, face_value, coupon_rate, years_to_maturity, ytm):
        self.face_value = face_value
        self.coupon_rate = coupon_rate
        self.years_to_maturity = years_to_maturity
        self.ytm = ytm

    def calculate_price(self):
        pass

    def calculate_yield_to_maturity(self):
        pass

    def calculate_duration(self):
        pass

    def calculate_convexity(self):
        pass

    def plot_yield_curve(self):
        pass

    def show_interest_rate_sensitivity(self):
        pass
