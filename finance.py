#!/usr/bin/env python

import math
import pandas as pd
import yfinance as yf
#import logging as log
import pickle
import json
from datetime import date

# Borrowed from StackOverflow lol
millnames = ['',' Thousand',' Million',' Billion',' Trillion']
def millify(n):
    n = float(n)
    millidx = max(0,min(len(millnames)-1,
                        int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

    return '{:.0f}{}'.format(n / 10**(3 * millidx), millnames[millidx])

class Stock:
    #PRIVATE

    ___ticker = 0
    ticker_invalid = False
    value_margin = 0
    price_book = 0
    price_earnings = 0
    price = 0
    shares_outstanding = 0
    market_cap = ''
    intrinsic_value = 0

    company_name = ''
    company_symbol = ''

    def __init__(self, ticker):
        try:
            print(ticker)
            self.__ticker = yf.Ticker(ticker)
            self.ticker_invalid = False
            self.company_symbol = ticker
        except:
            print("[ERROR] Invalid ticker input")
            self.ticker_invalid = True

    def __get_fcf(self, debug=False):
        fcf = []

        if self.ticker_invalid:
            fcf.append(0)
            return fcf

        stock_cashflows = self.__ticker.get_cashflow(as_dict="True")
        for date in stock_cashflows:
            try:
                operating_cashflow = stock_cashflows[date]["Total Cash From Operating Activities"]
                capex = stock_cashflows[date]["Capital Expenditures"]
            except:
                #print("Unable to find operating cashflow / capital expenditures...")
                fcf.append(0)
                return fcf
            if math.isnan(operating_cashflow) or math.isnan(capex):
                #print("[ERROR] NaN has been encountered during FCF calculation")
                fcf.append(0)
                return fcf
            if operating_cashflow == 0:
                fcf.append(0)
                return fcf
       
            free_cashflow = operating_cashflow - abs(capex)
            fcf.append(free_cashflow)
            if debug:
                print(date)
                print('FCF is ' + str(free_cashflow))

        return fcf

    #PUBLIC
    def get_avg_fcf(self):
        fcf_list = self.__get_fcf()
        if len(fcf_list) != 0:
            avg_fcf = sum(fcf_list) / len(fcf_list)
        else:
            return 0
        return avg_fcf

    def get_dcf_valuation(self, discount_rate_percent=11, growth_rate_percent=0, years_to_project=5):
        discount_rate = discount_rate_percent / 100
        growth_factor = (growth_rate_percent / 100) + 1 #growth factor to multiply by -- decimal not a percent
        avg_fcf = self.get_avg_fcf() #fetch averaged FCF of the past 4 years
        new_fcf = avg_fcf #average free cash flow after being multiplied by growth factor ... changes w/ loop

        new_fcf *= (growth_factor ** years_to_project)

        terminal_value = new_fcf / (discount_rate - (growth_factor - 1))
        return terminal_value

    def is_undervalued(self, discount_rate_percent=11, growth_rate_percent=0):
        try:
            stock_info = self.__ticker.get_info()
            self.company_name = stock_info['longName']
            self.shares_outstanding = stock_info['sharesOutstanding']
            self.price = stock_info['regularMarketPrice']

            if self.price == 0 or self.shares_outstanding == 0:
                return 0

            self.intrinsic_value = self.get_dcf_valuation(discount_rate_percent, growth_rate_percent) / self.shares_outstanding

            if self.intrinsic_value <= 0:
                return False
            elif (self.price / self.intrinsic_value) < 0.8:
                self.value_margin = abs((self.price - self.intrinsic_value) / self.intrinsic_value) * 100

                try:
                    self.price_book = stock_info['priceToBook']
                except:
                    self.price_book = 0
                try:
                    self.price_earnings = stock_info['trailingPE']
                except:
                    self.price_earnings = 0
                try:
                    self.market_cap = millify(stock_info['marketCap'])
                except:
                    self.market_cap = ''

                return True
            else:
                return False

        except:
            return False

def get_sorting_key(stock):
    return stock.value_margin

def load_json(filename):
    with open(filename, 'r') as f:
        data = f.read()
    stock_data = json.loads(data)

    undervalued_stocks = []
    for f in stock_data:
        stock = Stock(f['Symbol'])
        if stock.is_undervalued():
            undervalued_stocks.append(stock)
    return undervalued_stocks

def load_pickle(filename):
    with open(filename, 'rb') as f:
        stock_data = pickle.load(f)

    undervalued_stocks = []
    for f in stock_data:
        stock = Stock(f)
        if stock.is_undervalued():
            undervalued_stocks.append(stock)
    return undervalued_stocks

def dump_stocks(undervalued_list):
    with open("undervalued_stocks.txt", "a") as file_out:
        file_out.write("UNDERVALUED STOCKS | " + str(date.today()) + "\n\n")
        for s in undervalued_list:
            file_out.write("----------------\n" + s.company_name + " (" + s.company_symbol + ")\n")
            file_out.write("Value Margin: " + str(round(s.value_margin, 3)) + "%\n")
            file_out.write("Price: " + str(s.price) + " | Intrinsic Value: " + str(s.intrinsic_value) + "\n")
            file_out.write("P/B: " + str(s.price_book) + " | P/E (TTM): " + str(s.price_earnings) + "\n")
            file_out.write("Market Cap: " + s.market_cap + " | Shares Outstanding: " + str(s.shares_outstanding) + "\n")
            file_out.write("---------------- \n\n")
    print("-- FINISHED PROCESSING JSON --")

def process_data(undervalued_list):
    undervalued_list.sort(key=get_sorting_key, reverse=True)
    dump_stocks(undervalued_list)

#process_data(load_pickle('stock_list.p'))
stock = Stock('aal')
print(stock.is_undervalued())
print(stock.intrinsic_value)
print(stock.price)
