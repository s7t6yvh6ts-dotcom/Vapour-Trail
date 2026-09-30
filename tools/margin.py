#!/usr/bin/env python3
"""Margin check: what you actually keep per order, single units and bundles.

Example (pouches, all money in GBP):
  python3 tools/margin.py --cost 3.80 --price 6.00 --postage 1.55
  python3 tools/margin.py --cost 1.20 --ship 0.40 --duty 4 --price 6.00 --vat

  --cost     supplier price per unit
  --ship     freight per unit to your door (0 for UK wholesale with free delivery)
  --duty     import duty % on (cost + ship)
  --price    your single-unit shelf price (incl. VAT if you're VAT-registered)
  --vat      you're VAT-registered: 20% of the sale goes to HMRC
  --fee      card processing % (high-risk vape/nicotine accounts are usually 3-6%)
  --postage  your cost to post one order
  --target   minimum margin % you'll accept; bundles below it are flagged

Rows marked LOSS lose money on every order. Rows marked THIN are under --target.
"""
import argparse


def order_profit(n, unit_price, landed, a):
    revenue = n * unit_price
    net = revenue / 1.2 if a.vat else revenue
    fees = revenue * a.fee / 100 + a.fee_fixed
    profit = net - fees - n * landed - a.postage
    return revenue, profit, (profit / net * 100 if net else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cost", type=float, required=True)
    p.add_argument("--ship", type=float, default=0.0)
    p.add_argument("--duty", type=float, default=0.0)
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--vat", action="store_true")
    p.add_argument("--fee", type=float, default=4.5)
    p.add_argument("--fee-fixed", type=float, default=0.20)
    p.add_argument("--postage", type=float, default=0.0)
    p.add_argument("--target", type=float, default=25.0)
    p.add_argument("--sizes", default="1,3,5,10", help="bundle sizes to price")
    a = p.parse_args()

    landed = (a.cost + a.ship) * (1 + a.duty / 100)
    print(f"Landed cost per unit: £{landed:.2f}  (shelf price £{a.price:.2f}"
          f"{', VAT-registered' if a.vat else ''}, fees {a.fee}% + £{a.fee_fixed:.2f}, postage £{a.postage:.2f}/order)\n")

    print(f"{'BUNDLE':<8}{'DISCOUNT':<10}{'BUNDLE PRICE':<14}{'PROFIT/ORDER':<14}{'MARGIN':<8}")
    for n in (int(s) for s in a.sizes.split(",")):
        for disc in (0, 10, 15, 20) if n > 1 else (0,):
            unit_price = a.price * (1 - disc / 100)
            revenue, profit, margin = order_profit(n, unit_price, landed, a)
            flag = "LOSS" if profit < 0 else "THIN" if margin < a.target else ""
            print(f"{n:<8}{f'{disc}%':<10}{f'£{revenue:.2f}':<14}{f'£{profit:.2f}':<14}{f'{margin:.0f}%':<8}{flag}")
        print()


if __name__ == "__main__":
    main()
