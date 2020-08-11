#!/usr/bin/env python
import math
import yfinance as yf
#import logging as log
import pickle
import json
from datetime import date
import multiprocessing as mp

# Credit for millify: StackOverflow
millnames = ['',' Thousand',' Million',' Billion',' Trillion']
def millify(n):
    n = float(n)
    millidx = max(0,min(len(millnames)-1,
                        int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

    return '{:.0f}{}'.format(n / 10**(3 * millidx), millnames[millidx])

def is_valid_num(n):
    if math.isnan(n) or n is None:
        return False
    else:
        return True

class Stock:
    #PRIVATE
    ___ticker = 0
    ___stock_info = 0
    value_margin = 0
    price_book = 0
    price_earnings = 0
    price = 0
    shares_outstanding = 0
    intrinsic_value = 0

    company_name = ''
    company_symbol = ''
    market_cap = ''
    sector = ''
    industry = ''
    country = ''
    currency = ''

    def __init__(self, ticker):
        try:
            self.___ticker = yf.Ticker(ticker)
            self.company_symbol = ticker
        except:
            print("[ERROR] Invalid ticker input")

    def __get_fcf(self, debug=False):
        fcf = []
        '''
        if self.ticker_invalid:
            fcf.append(0)
            return fcf
        '''

        stock_cashflows = self.___ticker.get_cashflow(as_dict="True")
        for date in stock_cashflows:
            try:
                operating_cashflow = stock_cashflows[date]["Total Cash From Operating Activities"]
                capex = stock_cashflows[date]["Capital Expenditures"]
            except:
                #print("Unable to find operating cashflow / capital expenditures...")
                fcf.append(0)
                return fcf
            if not is_valid_num(operating_cashflow) or not is_valid_num(capex):
                #print("[ERROR] NaN has been encountered during FCF calculation")
                fcf.append(0)
                return fcf
            if operating_cashflow == 0:
                fcf.append(0)
                return fcf
       
            free_cashflow = operating_cashflow - abs(capex) #Absolute value just in case capex is expressed as negative
            fcf.append(free_cashflow)
        return fcf

    #PUBLIC
    def get_avg_fcf(self):
        fcf_list = self.__get_fcf()
        if len(fcf_list) != 0:
            return sum(fcf_list) / len(fcf_list)
        else:
            return 0 #Return 0 to indicate something is awry

    def get_dcf_valuation(self, discount_rate_percent=11, growth_rate_percent=0, years_to_project=5):
        discount_rate = discount_rate_percent / 100
        growth_factor = (growth_rate_percent / 100) + 1 #growth factor to multiply by -- decimal not a percent

        #average free cash flow after being multiplied by growth factor ... changes w/ loop
        new_fcf = self.get_avg_fcf() #fetch averaged FCF of the past 4 years

        new_fcf *= (growth_factor ** years_to_project)

        # found this math shortcut inadvertently. Includes terminal value and also averaged out DCF
        value = new_fcf / (discount_rate - (growth_factor - 1))
        return value

    def get_stock_info(self):

        #This is super messy but kind of necessary
        #Maybe make the stock data like a struct and use a for loop for it? idk

        try:
            self.price_book = self.___stock_info['priceToBook']
            if not is_valid_num(self.price_book):
                self.price_book = 0
        except:
            pass
        try:
            self.price_earnings = self.___stock_info['trailingPE']
            if not is_valid_num(self.price_earnings):
                self.price_earnings = 0
        except:
            pass
        try:
            self.market_cap = millify(self.___stock_info['marketCap'])
            if self.market_cap is None:
                self.market_cap = ""
        except:
            pass

        try:
            self.company_name = self.___stock_info['longName']
            if self.company_name is None:
                self.company_name = ""
        except:
            pass

        try:
            self.sector = self.___stock_info['sector']
            if self.sector is None:
                self.sector = ""
        except:
            pass

        try:
            self.industry = self.___stock_info['industry']
            if self.industry is None:
                self.industry = ""
        except:
            pass

        try:
            self.country = self.___stock_info['country']
            if self.country is None:
                self.country = ""
        except:
            pass

        try:
            self.currency = self.___stock_info['currency']
            if self.currency is None:
                self.currency = ""
        except:
            pass

    def is_undervalued(self, discount_rate_percent=11, growth_rate_percent=0):
        try:
            self.___stock_info = self.___ticker.get_info()

            self.shares_outstanding = self.___stock_info['sharesOutstanding']
            self.price = self.___stock_info['regularMarketPrice']

            self.intrinsic_value = self.get_dcf_valuation(discount_rate_percent, growth_rate_percent) / self.shares_outstanding
        except Exception as e:
#            traceback.print_exc()
            return False
            # If earnings are negative and intrinsic value is negative we don't want the stock
        if self.intrinsic_value <= 0:
            return False
        elif (self.price / self.intrinsic_value) < 0.8:
            # The sweet spot with DCF
            self.value_margin = abs((self.price - self.intrinsic_value) / self.intrinsic_value) * 100
            #print('\n\n')

            self.get_stock_info()
            return True
        else:
            return False
            #If the stock is overvalued according to DCF we also don't want it

class Manager:
    ___undervalued_stocks = []
    ___pool = None

    def __init__(self):
        self.___undervalued_stocks = []
        self.___pool = mp.Pool(mp.cpu_count())

    def get_sorting_key(self, stock):
        return stock.value_margin

    def read_json_symbol(self, obj):
        return Stock(obj['Symbol'])

    def read_pickle(self, obj):
        return Stock(obj)

    def dcf_test(self, stock):
        if stock.is_undervalued():
            return stock

    def dcf_compute(stock_obj_list):
        tmp1 = self.___pool.map(self.dcf_test, stock_obj_list)
        self.___undervalued_stocks = list(filter((None).__ne__, tmp1))

    def load_json(self, filename):
        with open(filename, 'r') as f:
            data = f.read()
        raw_stock_data = json.loads(data)
        stock_list = self.___pool.map(self.read_json_symbol, raw_stock_data)
        return stock_list

    def load_pickle(self, filename):
        with open(filename, 'rb') as f:
            raw_stock_data = pickle.load(f)
        stock_list = self.___pool.map(self.read_pickle, raw_stock_data)
        return stock_list

    def dump_stocks(self):
        with open("undervalued_stocks.txt", "a") as file_out:
            file_out.write("UNDERVALUED STOCKS | " + str(date.today()) + "\n\n")
            for s in self.___undervalued_stocks:
                file_out.write("----------------\n" + s.company_name + " (" + s.company_symbol + ")\n")
                file_out.write("Value Margin: " + str(round(s.value_margin, 3)) + "%\n")
                file_out.write("Price: " + str(s.price) + " | Intrinsic Value: " + str(s.intrinsic_value) + "\n")
                file_out.write("P/B: " + str(s.price_book) + " | P/E (TTM): " + str(s.price_earnings) + "\n")
                file_out.write("Market Cap: " + s.market_cap + " | Shares Outstanding: " + str(s.shares_outstanding) + "\n")
                file_out.write("Industry: " + s.sector + " | Sector: " + s.industry + "\n")
                file_out.write("Country: " + s.country + " | Currency: " + s.currency + "\n")
                file_out.write("---------------- \n\n")
        print("-- FINISHED PROCESSING JSON --")

    def process_data(self):
        self.___undervalued_stocks.sort(key=self.get_sorting_key, reverse=True)
        self.dump_stocks()

    # TODO: ADD DISCOUNT RATE AND GROWTH RATE
    def database_dcf_run(database_name):
        file_type = database_name.split(".", 1)[1]

        stock_list = []
        if file_type == "p": #pickle
            stock_list = self.load_pickle(database_name)
        elif file_type == "json":
            stock_list = self.load_json(database_name)
        else:
            print("INVALID FILETYPE")
            return 1
        self.dcf_compute(stock_list)
        self.process_data()


'''
        pool = mp.Pool(mp.cpu_count())
        stock_list = pool.map(self.read_json_symbol, stock_data)
        tmp1 = pool.map(self.dcf_test, stock_list)

        self.___undervalued_stocks = list(filter((None).__ne__, tmp1))
'''

#Why do we have to do this again when multiprocessing?
if __name__ == "__main__":
    obj = Manager()
    obj.load_json('sp500.json')
    obj.process_data()
