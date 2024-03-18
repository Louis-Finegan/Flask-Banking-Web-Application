import requests
import json
import os
from dotenv import load_dotenv
from flask import flash, redirect, url_for

class CurrencyExchanger(object):
    def __init__(self, sender_currency, receiver_currency, amount):
        self.currency_1 = sender_currency
        self.currency_2 = receiver_currency
        self.amount = amount

        load_dotenv()
        self.API_KEY = os.getenv('CURRENCYBEACON_KEY')
        self.API_ENDPOINT = f'https://api.currencybeacon.com/v1/convert?from={self.currency_1}&to={self.currency_2}&amount={self.amount}&api_key={self.API_KEY}'

    def api_call(self):
        return requests.get(self.API_ENDPOINT)
        
    def get_value(self, response):
        response_json = response.json()

        return response_json['value']