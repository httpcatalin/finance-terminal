import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentiment_data import get_fear_greed_index

def test_get_fear_greed_index():
    index = get_fear_greed_index()
    assert index is not None and 0 <= index <= 100
    print("get_fear_greed_index test passed")

if __name__ == "__main__":
    test_get_fear_greed_index()
    print("All tests passed!")