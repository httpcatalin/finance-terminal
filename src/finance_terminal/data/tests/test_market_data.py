import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_data import get_stock_prices, get_historical_volatility, get_futures_prices, get_risk_free_rate, get_bond_yields

def test_get_stock_prices():
    data = get_stock_prices('AAPL')
    assert data is not None and not data.empty
    print(f"get_stock_prices test passed")

def test_get_historical_volatility():
    vol = get_historical_volatility('AAPL')
    assert vol is not None and vol > 0
    print(f"get_historical_volatility test passed")

def test_get_futures_prices():
    data = get_futures_prices('GC=F') 
    assert data is not None and not data.empty
    print("get_futures_prices test passed")

def test_get_risk_free_rate():
    if not os.getenv('FRED_API_KEY'):
        print("skip test_get_risk_free_rate, FRED_API_KEY api key is not set")
        return
    rate = get_risk_free_rate()
    assert rate is not None
    print("get_risk_free_rate test passed")

def test_get_bond_yields():
    if not os.getenv('FRED_API_KEY'):
        print("skip test_get_bond_yields, FRED_API_KEY api key is not set")
        return
    yields = get_bond_yields()
    assert yields is not None
    print("get_bond_yields test passed")

if __name__ == "__main__":
    test_get_stock_prices()
    test_get_historical_volatility()
    test_get_futures_prices()
    test_get_risk_free_rate()
    test_get_bond_yields()
    print("All tests passed!")