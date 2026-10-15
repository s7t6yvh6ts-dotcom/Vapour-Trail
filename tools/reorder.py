#!/usr/bin/env python3
"""Reorder planner: tells you what to order from China, and by when.

Input CSV columns: sku,name,on_hand,sold_last_30d,lead_time_days
  - on_hand:        units in stock right now
  - sold_last_30d:  units sold in the last 30 days (Shopify: Analytics > Reports > Sales by product)
  - lead_time_days: order-to-your-door days in a normal month (air ~21, sea ~45)

Usage:
  python3 tools/reorder.py stock.csv                 # plan from today
  python3 tools/reorder.py stock.csv --today 2026-09-30 --safety-days 7

Chinese shutdowns (Golden Week, Chinese New Year) are added to the lead time
whenever an order placed on the order-by date would still be in the pipeline
during one, so the order-by date moves earlier automatically.
"""
import argparse
import csv
import math
import sys
from datetime import date, timedelta

# (name, first day factories stop, last day of disruption, extra days it adds to lead time)
CHINA_SHUTDOWNS = [
    ("Golden Week 2026", date(2026, 10, 1), date(2026, 10, 9), 10),
    ("Chinese New Year 2027", date(2027, 1, 30), date(2027, 2, 21), 25),
    ("Golden Week 2027", date(2027, 10, 1), date(2027, 10, 9), 10),
]


def effective_lead_time(order_date, base_lead):
    """Lead time for an order placed on order_date, including any shutdown it runs into."""
    lead = base_lead
    for _, start, end, extra in CHINA_SHUTDOWNS:
        if order_date <= end and order_date + timedelta(days=lead) >= start:
            lead += extra
    return lead


def plan_row(row, today, safety_days, cover_days):
    on_hand = int(row["on_hand"])
    daily = int(row["sold_last_30d"]) / 30
    base_lead = int(row["lead_time_days"])

    if daily == 0:
        return dict(row, daily="0.0", stockout="never", order_by="-", lead="-", order_qty=0, status="NO SALES")

    stockout = today + timedelta(days=math.floor(on_hand / daily))

    # Latest order date whose (shutdown-adjusted) delivery still lands `safety_days` before stockout.
    order_by = stockout - timedelta(days=base_lead + safety_days)
    while order_by > today - timedelta(days=365) and (
        order_by + timedelta(days=effective_lead_time(order_by, base_lead) + safety_days) > stockout
    ):
        order_by -= timedelta(days=1)

    lead_if_today = effective_lead_time(today, base_lead)
    # If the *next* order (placed ~cover_days from now) runs into a shutdown, this order
    # has to carry you through that too - this is what stops you running dry over CNY.
    next_order_delay = effective_lead_time(today + timedelta(days=cover_days), base_lead) - base_lead
    order_qty = max(0, math.ceil(
        daily * (lead_if_today + safety_days + cover_days + next_order_delay) - on_hand
    ))

    if order_by < today:
        status = "LATE - ORDER NOW"
    elif order_by <= today + timedelta(days=7):
        status = "ORDER THIS WEEK"
    else:
        status = "OK"

    return dict(
        row,
        daily=f"{daily:.1f}",
        stockout=stockout.isoformat(),
        order_by=order_by.isoformat(),
        lead=lead_if_today,
        order_qty=order_qty,
        status=status,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv_path")
    p.add_argument("--today", type=date.fromisoformat, default=date.today())
    p.add_argument("--safety-days", type=int, default=7, help="buffer so stock lands before you run out")
    p.add_argument("--cover-days", type=int, default=30, help="days of sales each order should cover")
    args = p.parse_args()

    with open(args.csv_path, newline="") as f:
        rows = [plan_row(r, args.today, args.safety_days, args.cover_days) for r in csv.DictReader(f)]

    order = {"LATE - ORDER NOW": 0, "ORDER THIS WEEK": 1, "OK": 2, "NO SALES": 3}
    rows.sort(key=lambda r: (order[r["status"]], r["order_by"]))

    cols = [("status", 16), ("sku", 14), ("name", 24), ("on_hand", 7), ("daily", 6),
            ("stockout", 10), ("order_by", 10), ("lead", 5), ("order_qty", 9)]
    print("  ".join(h.upper().ljust(w) for h, w in cols))
    for r in rows:
        print("  ".join(str(r[h])[:w].ljust(w) for h, w in cols))

    upcoming = [s for s in CHINA_SHUTDOWNS if s[2] >= args.today]
    if upcoming:
        name, start, end, _ = upcoming[0]
        print(f"\nNext China shutdown: {name}, {start:%d %b} - {end:%d %b %Y}.")


if __name__ == "__main__":
    sys.exit(main())
