# -*- coding:utf-8 -*-
"""
Created on 2015/10/20
@author: Jacob He
@contact: hezhenke123@163.com
"""
import os,sys
import pandas as pd
import lib.cons as ct
import lib.stock.trading as td
from lib.util import dateu as du
import json
import numpy as np
from pymongo import MongoClient
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request


def read_file_to_db(root_dir):
    
    if not os.path.isdir(root_dir):
        return False
    for _,_,filenames in os.walk(root_dir):
        for filename in filenames:
            if os.path.splitext(filename)[1] == '.txt':
                real_filename = os.path.splitext(filename)[0]
                code = real_filename.split('#')[1]
                print("reading %s history data\n"%(code))
                try:
                    
                    client = MongoClient(ct.MONGO_HOST, ct.MONGO_PORT)
                    
                    cursor = client[ct.MONGO_DATABASE]["history_data"].find({"code":code})
                    #if the code exist in the database,do nothing
                    if cursor.count() > 0:
                        continue
                    exchange = real_filename.split('#')[0]
                    txtfile = os.path.join(root_dir, filename)
                    df = read_df(code,txtfile)
                    if not isinstance(df, pd.DataFrame):
                        raise RuntimeError('data type is incorrect')
                        continue
                    df = df.reset_index()
                    print("writting %s history data to db \n"%(code))
                    #print json.loads(df.to_json(orient='records'))
                    client[ct.MONGO_DATABASE]["history_data"].insert(json.loads(df.to_json(orient='records')))
                    
                except Exception as e:
                    print(e)
def read_df(code,file_path):
    if os.path.isfile(file_path):
        file_obj = open(file_path,"r")
        temp_line_list = []
        for line in file_obj:
            temp_line_list.append(line.strip())
        hist_data = [dict([('date',l.split(";")[0]), ('open',float(l.split(";")[1])), ('high',float(l.split(";")[2])),  ('low',float(l.split(";")[3])), ('close',float(l.split(";")[4])), ('volume',int(l.split(";")[5]))])  for l in temp_line_list[:-1]]
        df = pd.DataFrame(hist_data)
        df.drop_duplicates("date")
        df= df.set_index("date")

        
        #get the fuquan data
        fuquan_df = _parase_fq_factor(code)
        if not isinstance(fuquan_df, pd.DataFrame):
            return None
        
        #add two columns 
        df.insert(len(df.columns), "factor",1)
        df.insert(len(df.columns), "adjclose",0)
        df.insert(len(df.columns), "code",code)
        rate = get_adj_rate(code,fuquan_df)
        for date in df.index:
            if date not in fuquan_df.index:
                df = df.drop(date)
                continue
            
            df.loc[date,'factor'] = round(fuquan_df.loc[date,'fqprice']/df.loc[date,'close'],4)
            df.loc[date,'adjclose'] = round(fuquan_df.loc[date,'fqprice']/rate,2)
        return df
def get_adj_rate(code,fuquan_df):
    frow = fuquan_df.head(1)
    rt = td.get_realtime_quotes(code)
    if rt is None:
        return None
    if ((float(rt['high']) == 0) & (float(rt['low']) == 0)):
        preClose = float(rt['pre_close'])
    else:
        if du.is_holiday(du.today()):
            preClose = float(rt['price'])
        else:
            if (du.get_hour() > 9) & (du.get_hour() < 18):
                preClose = float(rt['pre_close'])
            else:
                preClose = float(rt['price'])
    
    rate = float(frow['fqprice']) / preClose
    return rate
        
def _parase_fq_factor(code):
    symbol = _code_to_symbol(code)
    try:
        request = Request(ct.HIST_FQ_FACTOR_URL%(symbol))
        request.add_header("User-Agent", ct.USER_AGENT)
        text = urlopen(request, timeout=20).read()
        text = text[1:len(text)-1]
        text = text.decode('utf-8') if ct.PY3 else text
        text = text.replace('{_', '{"')
        text = text.replace('total', '"total"')
        text = text.replace('data', '"data"')
        text = text.replace(':"', '":"')
        text = text.replace('",_', '","')
        text = text.replace('_', '-')
        text = json.loads(text)
        df = pd.DataFrame({'date':list(text['data'].keys()), 'fqprice':list(text['data'].values())})
        df['date'] = df['date'].map(_fun_except) # for null case
        if df['date'].dtypes == np.object:
            df['date'] = df['date'].astype(np.str)
        df = df.drop_duplicates('date')
        df = df.sort('date', ascending=False)
        df = df.set_index("date")
        df['fqprice'] = df['fqprice'].astype(float)
        return df
    except Exception as e:
        print(e)
    

def _code_to_symbol(code):
    """
        add the exchange to the stock symbol
    """
    if code in ct.INDEX_LABELS:
        return ct.INDEX_LIST[code]
    else:
        if len(code) != 6 :
            return ''
        else:
            return 'sh%s'%code if code[:1] in ['5', '6'] else 'sz%s'%code
        
def _fun_except(x):
    if len(x) > 10:
        return x[-10:]
    else:
        return x

if __name__ == '__main__':
    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_root_dir = os.path.join(project_root_dir,"data","stockdata")
    read_file_to_db(data_root_dir)   
           
        