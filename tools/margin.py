#!/usr/bin/env python3
"""Margin check: what you actually keep per order, single units and bundles.

Example (pouches, all money in GBP):
  python3 tools/margin.py --cost 3.80 --price 6.00 --postage 1.55
  python3 tools/margin.py --cost 1.20 --ship 0.40 --duty 4 --imported --price 6.00 --postage 1.55

  --cost      what you pay the supplier per unit, including any VAT you can't claim back
  --ship      freight per unit to your door (0 for UK wholesale with free delivery)
  --duty      import duty % on (cost + ship)
  --excise    UK excise duty per unit in £ that isn't already in --cost. Vaping Products Duty
              (from 1 Oct 2026) is £2.20 per 10 ml of e-liquid; UK duty-paid prices include it
  --imported  you pay 20% import VAT at the border (goods from outside the UK). If you're not
              VAT-registered you can't claim it back, so it's added. Leave it off if the
              seller already charged UK VAT at checkout (usual for orders of £135 or less)
  --price     your single-unit shelf price (incl. VAT if you're VAT-registered)
  --vat       you're VAT-registered: 20% of the sale goes to HMRC, and you reclaim import VAT
  --fee       card processing % (high-risk vape/nicotine accounts are usually 3-6%)
  --postage   your cost to post one order
  --target    minimum margin % you'll accept; bundles below it are flagged

Rows marked LOSS lose money on every order. Rows marked THIN are under --target.
"""
import argparse
import math


def money(x):
    return f"-£{-x:.2f}" if x < 0 else f"£{x:.2f}"


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
    p.add_argument("--excise", type=float, default=0.0)
    p.add_argument("--imported", action="store_true")
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--vat", action="store_true")
    p.add_argument("--fee", type=float, default=4.5)
    p.add_argument("--fee-fixed", type=float, default=0.20)
    p.add_argument("--postage", type=float, default=0.0)
    p.add_argument("--target", type=float, default=25.0)
    p.add_argument("--sizes", default="1,3,5,10", help="bundle sizes to price")
    a = p.parse_args()

    try:
        sizes = [int(s) for s in a.sizes.split(",")]
    except ValueError:
        p.error(f"--sizes must be whole numbers separated by commas, e.g. 1,3,5,10 (got {a.sizes!r})")
    if a.price <= 0 or min(sizes) < 1:
        p.error("--price and every bundle size must be more than 0")
    money_args = (a.cost, a.ship, a.duty, a.excise, a.price, a.fee, a.fee_fixed, a.postage, a.target)
    if not all(math.isfinite(x) for x in money_args):
        p.error("every amount must be a number")
    if min(a.cost, a.ship, a.duty, a.excise, a.fee, a.fee_fixed, a.postage) < 0:
        p.error("costs, duties, fees and postage can't be negative")

    landed = (a.cost + a.ship) * (1 + a.duty / 100) + a.excise
    import_vat = a.imported and not a.vat
    if import_vat:
        landed *= 1.2
    print(f"Landed cost per unit: {money(landed)}{' incl. 20% import VAT' if import_vat else ''}"
          f"  (shelf price {money(a.price)}{', VAT-registered' if a.vat else ''}, "
          f"fees {a.fee:g}% + {money(a.fee_fixed)}, postage {money(a.postage)}/order)\n")

    print(f"{'BUNDLE':<8}{'DISCOUNT':<10}{'BUNDLE PRICE':<14}{'PROFIT/ORDER':<14}{'MARGIN':<8}")
    for n in sizes:
        for disc in (0, 5, 10, 15, 20) if n > 1 else (0,):
            unit_price = a.price * (1 - disc / 100)
            revenue, profit, margin = order_profit(n, unit_price, landed, a)
            flag = "LOSS" if profit < 0 else "THIN" if margin < a.target else ""
            print(f"{n:<8}{f'{disc}%':<10}{money(revenue):<14}{money(profit):<14}{f'{margin:.0f}%':<8}{flag}")
        print()
    if any(n > 1 for n in sizes):
        print("From 29 Oct 2026, a substantial discount to promote vapes or pouches is an offence. "
              "Keep bundle deals small.")


if __name__ == "__main__":
    main()
