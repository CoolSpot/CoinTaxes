#!/usr/bin/env python
import argparse

import os
import yaml

import exchanges
from formats import fill_8949, turbo_tax


def get_exchange(name, config):
    """Gets the exchange object based on the name and instantiates it

    Source: https://stackoverflow.com/a/1176180/2965993

    :param name: exchange name
    :param config: exchange configuration
    :return:
    """
    return getattr(exchanges, name.title())(config)


def fix_orders(exchange, buys, sells):
    """

    :param exchange:
    :param buys:
    :param sells:
    :return:
    """
    buys_fixed = []
    sells_fixed = []
    for orders in [buys, sells]:
        for order in orders:
            # See if the exchange currency is BTC
            # if order[6] == 'BTC':
            if order['currency'] == 'BTC':
                # This is a coin-coin transaction
                # We need to get the btc value in $$ and create another trade (a sell order)
                price_usd = exchange.get_price(order['order_time'], product='BTC-USD')
                cost_btc = order['cost']
                cost_usd = cost_btc * price_usd
                cost_per_coin_usd = cost_usd / order['amount']
                # get the coin name
                product = order['product']
                # Fix any coin discrepancies (right now call all bitcoin cash BCH, sometimes it is called BCC)
                if product == 'BCC':
                    product = 'BCH'
                if order['buysell'] == 'buy':
                    buys_fixed.append([
                        order['order_time'], product, 'buy', cost_usd, order['amount'], cost_per_coin_usd, 'USD'
                    ])
                    sells_fixed.append([
                        order['order_time'], 'BTC', 'sell', cost_usd, order['cost'], price_usd, 'USD'
                    ])
                elif order['buysell'] == 'sell':
                    sells_fixed.append([
                        order['order_time'], product, 'sell', cost_usd, order['amount'], cost_per_coin_usd, 'USD'
                    ])
                    buys_fixed.append([
                        order['order_time'], 'BTC', 'buy', cost_usd, order['cost'], price_usd, 'USD'
                    ])
                else:
                    print("WEIRD! Unknown order buy sell type!")
                    print(order)
            else:
                # This order was already paid/received with USD
                if order['buysell'] == 'buy':
                    buys_fixed.append(order)
                elif order['buysell'] == 'sell':
                    sells_fixed.append(order)
                else:
                    print("WEIRD! Unknown order buy/sell type!")
                    print(order)
    return buys_fixed, sells_fixed


def main():
    """

    :return:
    """
    parser = argparse.ArgumentParser(description='CoinTaxes', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--input', default='config.yml',
                        help='Configuration file to read.')
    args = parser.parse_args()

    # create output directory
    if not os.path.exists("output"):
        os.makedirs("output")

    # read yaml config file
    with open(args.input, 'r') as f:
        config = yaml.load(f.read())

    # also shares the name in the configs
    # exchanges_supported = ['gdax', 'coinbase', 'bittrex', 'gemini', 'poloniex']
    exchanges_supported = ['gdax', 'coinbase']

    buys = []
    sells = []

    # go through all supported exchanges
    for exchange_name in exchanges_supported:
        # instantiate the exchange and aggregate the buys and sells
        if exchange_name in config:
            exchange = get_exchange(exchange_name, config[exchange_name])
            if exchange_name == 'bittrex':
                exchange_buys, exchange_sells = exchange.get_buys_sells(order_file=config['bittrex']['file'])
            else:
                exchange_buys, exchange_sells = exchange.get_buys_sells()
            exchange_buys, exchange_sells = fix_orders(exchange, exchange_buys, exchange_sells)
            buys += exchange_buys
            sells += exchange_sells

    # Go through the buys and sells and see if they are coin-coin transactions
    # Converting means that coin-coin transactions are now coin-usd, usd-coin
    # print('Converting coin-coin transactions to usd-coin transactions...')
    # buys_fixed = []
    # sells_fixed = []

    # b, s = fix_orders([buys, sells])
    # buys_fixed += b
    # sells_fixed += s

    # for orders in [coinbase_buys, coinbase_sells, gdax_buys, gdax_sells, bittrex_buys, bittrex_sells]:
    # for orders in [coinbase_buys, coinbase_sells, gdax_buys, gdax_sells]:
    # for orders in [buys, sells]:
    #     b, s = fix_orders(orders)
    #     buys_fixed += b
    #     sells_fixed += s

    # sort the buys and sells by date
    print('Sorting the buy and sell orders by time')
    buys_sorted = sorted(buys, key=lambda buy_order: buy_order['order_time'])
    sells_sorted = sorted(sells, key=lambda buy_order: buy_order['order_time'])

    # Get the full order information to be used on form 8949
    full_orders = fill_8949.get_cost_basis(
        sells_sorted,
        buys_sorted,
        basis_type='highest',
        tax_year=config['year']
    )

    # Save the files in a pickle
    # pickle.dump([buys_sorted, sells_sorted, full_orders], open("save.p", "wb"))

    # Make the Turbo Tax import file
    if 'txf' in config and config['txf']:
        turbo_tax.make_txf(full_orders, year=config['year'])

    # Make the 8949 forms
    fill_8949.makePDF(full_orders, "test", config['name'], '-')


if __name__ == '__main__':
    main()
