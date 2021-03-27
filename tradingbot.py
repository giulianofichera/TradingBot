import json
import requests
import time
from get_api_key import get_api_key

base = 'ETH'
quote = 'USDC'
orders_info = []
current_user_orders_ids = []

### ------------ Convert possible order book items to float ------------
def convert_order_book_to_float(data_order_book):
	for side in data_order_book.keys():
		if type(data_order_book[side]) == list:
			for i in range(len(data_order_book[side])):
				for key,value in data_order_book[side][i].items():
					try:
						data_order_book[side][i][key] = float(value)
					except (ValueError, TypeError):
						pass


### ------------ Updates order book data ------------
def update_data_order_book():
	order_book_url = f'https://api.exchange.ripio.com/api/v1/orderbook/{base}_{quote}'
	data_order_book = requests.get(order_book_url)
	data_order_book = data_order_book.json()
	convert_order_book_to_float(data_order_book)

	return data_order_book


### ------------ Gathers all data required for the operation to take place ------------
### Works for all pairs
def info_base_quote(base = 'ETH',quote = 'USDC'):
	
	rate_url = f'https://api.exchange.ripio.com/api/v1/rate/{base}_{quote}/'
	order_book_url = f'https://api.exchange.ripio.com/api/v1/orderbook/{base}_{quote}'
	trade_history_url = f'https://api.exchange.ripio.com/api/v1/tradehistory/{base}_{quote}/'

	data = requests.get(rate_url)
	data = data.json()

	data_order_book = requests.get(order_book_url)
	data_order_book = data_order_book.json()

	data_trade_history = requests.get(trade_history_url)
	data_trade_history = data_trade_history.json()
	
	# Convert possible data items to float
	for key,value in data.items():
		try:
			data[key] = float(value)
		except (ValueError, TypeError):
			pass
	
	# Convert possible order book items to float
	convert_order_book_to_float(data_order_book)
	
	# Convert possible trade history items to float
	for i in range(len(data_trade_history)):
		for key,value in data_trade_history[i].items():
					try:
						data_trade_history[i][key] = float(value)
					except (ValueError, TypeError):
						pass
	
	pair = str(data['base']) + ' - ' + str(data['quote'])

	spread = round((data_order_book['sell'][0]['price'] - data_order_book['buy'][0]['price']),2)
	spread_percentage = round(spread * 100 / ((data['bid'] + data['ask'])/2),2)

	info = {
			'Pair': pair,
			'Last Price': data['last_price'],
			'Side': data_trade_history[0]['side'],
			'Low 24hs': data['low'],
			'High 24hs': data['high'],
			'Variation': data['variation'],
			f'Volume 24hs {base}': data['volume'],
			'Base': data['base'],
			'Base Name': data['base_name'],
			'Quote': data['quote'],
			'Quote Name': data['quote_name'],
			'Ask price (seller)': data['ask'],
			'Bid price (buyer)': data['bid'],
			'Spread': spread,
			'Spread Percentage': spread_percentage,
			'Avg': data['avg'],
			f'Ask Volume (seller) {quote}': data_order_book['sell'][0]['total'],
			f'Bid Volume (buyer) {quote}': data_order_book['buy'][0]['total'],
			f'Ask Volume (seller) {base}': data_order_book['sell'][0]['amount'],
			f'Bid Volume (buyer) {base}': data_order_book['buy'][0]['amount'],
			'Timestamp': data['created_at'], # ----------------> doesn't update as often???
			'Updated_id': data_order_book['updated_id']
			}

	return info, data, data_order_book, data_trade_history


### ------------ Defines the market trend taking into account the last 5 exchange sides ------------
def market_trend(data_trade_history):
	buy_count = 0
	sell_count = 0

	for i in range(5):
		if data_trade_history[i]['side'] == 'SELL':
			sell_count += 1
		else:
			buy_count += 1
	
	if sell_count > buy_count:
		return 'Decreasing'
	else:
		return 'Increasing'


### ------------ Creates the exchange order ------------
def create_order(base, quote, my_new_offer, side):

	api_key = get_api_key()

	url = f'https://api.exchange.ripio.com/api/v1/order/{base}_{quote}/'

	amount = round((11/my_new_offer), 4)

	body = {
		"order_type": "LIMIT",
		"amount": str(amount),
		"limit_price": str(my_new_offer),
		"side": side
	}

	headers = {
		"Content-Type" : "application/json",
		"Authorization" : f"Bearer {api_key}"
	}

	#### RUN IN TRY BLOCK TO CHECK FOR ERRORS
	response = requests.post(url=url, data=json.dumps(body), headers=headers)
	
	r = json.loads(response.text)
	print('Order id: ' + r['order_id'])

	return response


### ------------ Makes an order 0.01 higher on BUY side, 0.01 lower on SELL side ------------
def make_better_offer(data_order_book, base, quote, side, difference_best_offer):
	
	if side == 'BUY':
		my_new_offer = round(data_order_book['buy'][0]['price'] + difference_best_offer, 2)
		print('Buy order price: ' + str(data_order_book['buy'][0]['price']))
	
	if side == 'SELL':
		my_new_offer = round(data_order_book['sell'][0]['price'] - difference_best_offer, 2)
		print('Sell order price: ' + str(data_order_book['sell'][0]['price']))
	
	print(f'Ordering {my_new_offer}')

	# Make order of my_new_offer on exchange
	response = create_order(base, quote, my_new_offer, side)

	# Save order to global variable
	response = json.loads(response.text)
	print(response)
	
	new_order_info = {
		'order_id': response['order_id'],
		'price': response['limit_price'],
		'pair': response['pair'],
		'side': response['side'],
		'created_at': response['created_at'],
		'amount': response['amount']
	}

	orders_info.append(new_order_info)

	return my_new_offer


#Checks for bots working on the buy side by making an offer and watching if bots react	
def check_buy_side(difference_best_offer = 0.01):
	
	count = 0
	data_order_book = update_data_order_book()
	best_offer = data_order_book['buy'][0]['price']
	my_new_offer = make_better_offer(data_order_book, base, quote, 'BUY', difference_best_offer = difference_best_offer)

	# Check if bots made a better offer for 15 seconds, if not timeout
	while my_new_offer >= best_offer and count < 15:

		data_order_book = update_data_order_book()
		best_offer = data_order_book['buy'][0]['price']

		if my_new_offer >= best_offer:
			time.sleep(1)
			count += 1
			print(str(count) + '...')
		else:
			print('Bot operating on buy side\n')
			return True, my_new_offer
	
	print('Bot NOT operating on buy side\n')
	return False, -1


#Checks for bots working on the sell side by making an offer and watching if bots react	
def check_sell_side(difference_best_offer = 0.01):
	
	count = 0
	data_order_book = update_data_order_book()
	best_offer = data_order_book['sell'][0]['price']
	my_new_offer = make_better_offer(data_order_book, base, quote, 'SELL', difference_best_offer = difference_best_offer)

	# Check if bots made a better offer for 15 seconds, if not timeout
	while my_new_offer <= best_offer and count < 15:

		data_order_book = update_data_order_book()
		best_offer = data_order_book['sell'][0]['price']

		if my_new_offer <= best_offer:
			time.sleep(1)
			count += 1
			print(str(count) + '...')
		else:
			print('Bot operating on sell side\n')
			return True, best_offer
	
	print('Bot NOT operating on buy side\n')
	return False, -1


### ------------ Checks if bots are running on both buy and sell sides ------------
### Starts from the opposite side than the trend (if there's an increasing trend, start from buy side)
def check_bots_running (trend, data_order_book, base, quote):

	bot_running_buy_side = False
	bot_running_sell_side = False

	### If increasing, execute test on BUY side first, then SELL side
	if trend == 'Increasing':
		bot_running_buy_side, _ = check_buy_side()

		# If bot is operating on buy side, try sell side
		if bot_running_buy_side == True:
			bot_running_sell_side, _ =  check_sell_side()

		if bot_running_buy_side == True and bot_running_sell_side == True:
			print('Bots operating on both sides\n')
			return True

	### If decreasing, execute test on SELL side first, then BUY side
	if trend == 'Decreasing':
		bot_running_sell_side, _ = check_sell_side()

		# If bot is operating on buy side, try sell side
		if bot_running_sell_side == True:
			bot_running_buy_side, _ =  check_buy_side()

		if bot_running_buy_side == True and bot_running_sell_side == True:
			print('Bots operating on both sides\n')
			return True
	
	return False

### ------------ Checks spread between best buy and sell orders ------------
def check_spread(base, quote):
	data_order_book = update_data_order_book()

	spread = round((data_order_book['sell'][0]['price'] - data_order_book['buy'][0]['price']),2)
	spread_percentage = round(spread * 100 / ((data['bid'] + data['ask'])/2),2)

	return spread, spread_percentage

def get_best_value_sell():

	count = 0
	
	while True:
		
		# Make better offer, 5% better of the current spread
		bot_operating_sell_side, best_offer = check_sell_side(difference_best_offer = (spread * 0.05))

		if bot_operating_sell_side == True:
			count += 1
		else:
			break
		
	if count == 0:
		return False, -1
	else:
		return True, best_offer

def get_best_value_buy():

	count = 0
	
	while True:
		
		# Make better offer, 5% better of the current spread
		bot_operating_buy_side, best_offer = check_buy_side(difference_best_offer = (spread * 0.05))

		if bot_operating_buy_side == True:
			count += 1
		else:
			break
		
	if count == 0:
		return False, -1
	else:
		return True, best_offer

### ------------ Get order ids from current user and stores them in current_user_orders_ids ------------

def get_user_current_orders():
	
	api_key = get_api_key()

	url = f'https://api.exchange.ripio.com/api/v1/order/{base}_{quote}/?status=OPEN,PART/'

	headers = {
		"Content-Type" : "application/json",
		"Authorization" : f"Bearer {api_key}"
	}

	#### RUN IN TRY BLOCK TO CHECK FOR ERRORS
	response = requests.get(url=url, headers=headers)
	response = json.loads(response.text)

	for order in response['results']['data']:
		print(order['order_id'])
		current_user_orders_ids.append(order['order_id'])

	return response


### ------------ Cancel all user orders in current_user_orders_ids ------------
# Function get_user_current_orders is advised to be used first.

def cancel_all_user_current_orders():
	
	api_key = get_api_key()

	for order_id in current_user_orders_ids:

		url = f'https://api.exchange.ripio.com/api/v1/order/{base}_{quote}/{order_id}/cancel/'

		headers = {
		"Content-Type" : "application/json",
		"Authorization" : f"Bearer {api_key}"
		}


		print(f'Cancelling order {order_id}')
		response = requests.post(url=url, headers=headers)

		print(response.text)


###################### modify later after test are finished base and quote.
###################### make option to choose pairs (ETH_USDC, BTC_USDC, USDC_ARS)

print('')

info, data, data_order_book, data_trade_history = info_base_quote(base, quote)

for key,value in info.items():
	print(key + ': ' + str(value))


trend = market_trend(data_trade_history)
print('\n' + trend)


bots_running_both_sides = check_bots_running(trend, data_order_book, info['Base'], info['Quote'])

print('Other bots running: ' + str(bots_running_both_sides))

if bots_running_both_sides == True:
	#check spread again
	spread , spread_percentage = check_spread(info['Base'], info['Quote'])
	print(f'Spread: {spread}\nSpread percentage: {spread_percentage}')

	if spread_percentage > 5:
		print('Spread higher than 5%')
	
	best_value_sell = get_best_value_sell()
	best_value_buy = get_best_value_buy()


print(f'\nOrders created:\n{orders_info}')

get_user_current_orders()
print(f'Current user orders:\n{current_user_orders_ids}')

cancel_all_user_current_orders()