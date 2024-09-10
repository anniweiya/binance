

import hmac,hashlib,json,logging,time,websocket,traceback,os
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
import _thread as thread
from collections import OrderedDict
from urllib.parse import urlencode
logger = logging.getLogger("myLogger")
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s %(filename)s,行%(lineno)s \t %(levelname)s:%(message)s"))
file_handler = logging.FileHandler('binance.log')
file_handler.setFormatter(logging.Formatter("%(asctime)s %(filename)s,行%(lineno)s \t %(levelname)s:%(message)s"))
logger.addHandler(stream_handler)
logger.addHandler(file_handler)

uri = "wss://ws-fapi.binance.com/ws-fapi/v1"

def auto_trade(ws, datas):
    profit_rate = Decimal(datas['result']['totalUnrealizedProfit']) /  Decimal(datas['result']['totalWalletBalance']) * 100
    total = sum(abs(Decimal(position['positionAmt'])) * Decimal(position['entryPrice']) for position in datas['result']['positions'])
    leverage = total / Decimal(datas['result']['totalWalletBalance'])
    logger.info('总收益率情况{}总未实现盈亏{}总资产{}总持仓{}总杠杆{}'.format(str(profit_rate), \
            datas['result']['totalUnrealizedProfit'], datas['result']['totalWalletBalance'], total, leverage))
    for position in datas['result']['positions']:
        position_profit_rate = Decimal(position['unrealizedProfit']) / abs(Decimal(position['positionAmt'])) \
                                / Decimal(position['entryPrice']) * 100
        position_total = abs(Decimal(position['positionAmt'])) * Decimal(position['entryPrice'])
        timediff = datetime.utcfromtimestamp(int(time.time())) - datetime.utcfromtimestamp(int(position['updateTime']/1000))

        logger.info('当前{}收益率情况{}成本价{}未实现盈亏{}持仓{}持仓时间{}'.format(position['symbol'], \
            str(position_profit_rate), position['entryPrice'], position['unrealizedProfit'], position_total, str(timediff)))
        stop_market_trade_data = stop_market_trade(position, 10, win = -1)
        logger.info('无条件-10%止损单'  + stop_market_trade_data)
        ws.send(stop_market_trade_data)

            
        if (profit_rate < -10) :
            close_position_data = close_position(position)
            logger.info('Y2qPLVjpOuTzLs 按市价减仓，时间{}总收益率{}数据{}'.format(str(timediff), profit_rate, close_position_data))
            ws.send(close_position_data)



def stop_market_trade(position, factor, win = 1, type = 'STOP_MARKET'):
    side = "SELL" if Decimal(position['positionAmt']) > 0 else 'BUY'
    newClientOrderId = "{}_{}_{}_{}".format(position["symbol"], position['positionSide'], side, str(factor).replace('.', ''))

    if win >= 1 and Decimal(position['positionAmt']) > 0 : 
        dir = 1 # 多单止盈
    elif win < 1 and Decimal(position['positionAmt']) > 0:
        dir = -1  # 多单止损
    elif win >= 1 and Decimal(position['positionAmt']) <= 0:
        dir = -1 # 空单止盈
    else :
        dir = 1 # 空单止损
        
    price = str((Decimal(position['entryPrice']) * Decimal(100 + factor * dir) / 100).quantize(get_quantize(position["symbol"])))
    
    params = {
        "apiKey": apiKey,
        "symbol": position["symbol"],
        "side": side,
        'positionSide': position['positionSide'],
        "type": type,
        "quantity": str(abs(Decimal(position['positionAmt']))),
        "newClientOrderId": newClientOrderId,
        "stopPrice": price,
        "timestamp": int(time.time() * 1000)
    }
    
    params["signature"] = hmac_hashing(params)
    return json.dumps({
        "id": newClientOrderId ,
        "method": "order.place",
        "params": params
    })


def get_quantize(symbol):
    with open('exchangeInfo.json') as user_file:
      file_contents = user_file.read()    
    exchangeInfo = json.loads(file_contents)
    target_symbol = [e_symbol for e_symbol in exchangeInfo['symbols'] if e_symbol['symbol'] == symbol]
    target_f = [f for f in target_symbol[0]['filters'] if f['filterType'] == 'PRICE_FILTER']    
    return Decimal(target_f[0]['tickSize']).normalize()

def json_message(ws, datas):
    if datas.get('id') is not None and datas['id'] == 'get_account_status' :
        datas['result']['assets'] = [data for data in datas['result']['assets'] if Decimal(data['walletBalance']) > 0]
        datas['result']['positions'] = [data for data in datas['result']['positions'] if Decimal(data['initialMargin']) > 0]
        logger.info('收到binance查询资产情况:' + json.dumps(datas))
        auto_trade(ws, datas)
    else:
        logger.info('9VbKfCnbx0y9fx收到biance消息:' + json.dumps(datas))



def on_message(ws, message):
    logger.info('收到binance消息长度:' + str(len(message)))
    try: 
        json_message(ws, json.loads(message))
    except Exception as e:
        traceback.print_exc()
        logger.error('收到biance消息出错:' + message)


def hmac_hashing(data):
        return hmac.new(secret.encode("utf-8"), 
            urlencode(OrderedDict(sorted(data.items()))).encode("utf-8"), 
            hashlib.sha256).hexdigest()   
    

def on_open(ws):
    def run(*args):
        while True:
            data= get_account_status()
            ws.send(data)
            logger.info('币安websocket监听发送查询账户数据' + data)
            time.sleep(600)
    thread.start_new_thread(run, ())


def on_error(ws, error):
    logger.error(error)
    
def on_close(ws, a, b):
    logger.info("### websocket closed ###")
    

def get_account_status():
    params = {
        "apiKey": apiKey,
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = hmac_hashing(params)
    return json.dumps({
        "id": "get_account_status",
        "method": "account.status",
        "params": params
    })

def close_position(position):
    params = {
        "apiKey": apiKey,
        "quantity": str(abs(Decimal(position['positionAmt']))),
        "side": "SELL" if Decimal(position['positionAmt']) > 0 else 'BUY',
        "symbol": position["symbol"],
        "timestamp": int(time.time() * 1000),
        "type": "MARKET",
        'positionSide': position['positionSide']
    }
    
    params["signature"] = hmac_hashing(params)
    return json.dumps({
        "id": "close_position",
        "method": "order.place",
        "params": params
    })


def exchange(*args):
    while True:
        os.system('curl  -x "http://192.168.0.168:20171" \
                        -X GET "https://fapi.binance.com/fapi/v1/exchangeInfo" \
                        -o exchangeInfo.json')
        logger.info('exchangeInfo获取成功')
        time.sleep(86400)

def websocket_trade():
    while True:
        try:
            logger.info("### 准备连接binance ###")
            ws = websocket.WebSocketApp(uri, on_open=on_open,
                                      on_message = on_message,
                                      on_error = on_error,
                                      on_close = on_close)
            ws.run_forever(ping_interval=10, ping_timeout=9, http_proxy_host='192.168.0.168', http_proxy_port='20171', proxy_type='http')
        except Exception as e:
            traceback.print_exc()
            logger.error('连接binance出错')

        finally:
            time.sleep(60)


def start():
    thread.start_new_thread(exchange, ())
    websocket_trade()

def hello():
    print('binance')