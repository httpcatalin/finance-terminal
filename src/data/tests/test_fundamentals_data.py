import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fundamentals_data import get_income_statement, get_balance_sheet, get_cash_flow

def test_get_income_statement():
    stmt = get_income_statement('AAPL')
    assert stmt is not None and not stmt.empty
    print(stmt.head())
    print("get_income_statement test passed")

def test_get_balance_sheet():
    sheet = get_balance_sheet('AAPL')
    assert sheet is not None and not sheet.empty
    print(sheet.head())
    print("get_balance_sheet test passed")

def test_get_cash_flow():
    flow = get_cash_flow('AAPL')
    assert flow is not None and not flow.empty
    print(flow.head())
    print("get_cash_flow test passed")

if __name__ == "__main__":
    test_get_income_statement()
    test_get_balance_sheet()
    test_get_cash_flow()
    print("All tests passed!")