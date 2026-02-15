import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

def get_fear_greed_index():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        index = int(data['data'][0]['value'])
        return index
    except Exception as e:
        logging.error(f"Error fetching Fear & Greed index: {e}")
        return None