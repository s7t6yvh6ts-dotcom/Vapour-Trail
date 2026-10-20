#!/usr/bin/env python3
"""Reorder planner: tells you what to order, how much, and by when.

Input CSV columns: sku,name,on_hand,sold_last_30d,lead_time_days[,on_order][,origin]
  - on_hand:        units in stock right now
  - sold_last_30d:  units sold in the last 30 days (from your shop's sales-by-product report)
  - lead_time_days: order-to-your-door days in a normal month (China air ~21, sea ~45, UK wholesale 1-2)
  - on_order:       optional. Units already ordered that haven't arrived yet. Fill this in,
                    or the planner will tell you to order the same stock twice.
  - origin:         optional. "China" (the default if blank), "UK" or "EU". Chinese shutdowns
                    only delay stock from China. Anything it doesn't recognise is treated as
                    China, with a warning, so an order is never planned too late.

Usage:
  python3 tools/reorder.py stock.csv                 # plan from today
  python3 tools/reorder.py stock.csv --today 2026-09-30 --safety-days 7

Chinese shutdowns (Golden Week, Chinese New Year) are added to the lead time
whenever an order placed on the order-by date would still be in the pipeline
during one, so the order-by date moves earlier automatically. If the next order
after this one runs into a shutdown, this order is made bigger to carry you through.
"""
import argparse
import csv
import io
import math
import sys
from datetime import date, timedelta

# (name, first day of disruption, last day of disruption, extra days it adds to lead time).
# Windows run from about a week before the official holiday to a week or two after it.
# Check each year's official dates when the State Council publishes them (usually November).
CHINA_SHUTDOWNS = [
    ("Golden Week 2026", date(2026, 10, 1), date(2026, 10, 9), 10),
    ("Chinese New Year 2027", date(2027, 1, 30), date(2027, 2, 21), 25),
    ("Golden Week 2027", date(2027, 10, 1), date(2027, 10, 9), 10),
    ("Chinese New Year 2028", date(2028, 1, 19), date(2028, 2, 10), 25),
]

STATUS_ORDER = {"LATE - ORDER NOW": 0, "ORDER THIS WEEK": 1, "OK": 2, "NO SALES": 3}
NOT_CHINA = {"uk", "gb", "united kingdom", "great britain", "england", "scotland", "wales",
             "northern ireland", "eu", "europe"}


def effective_lead_time(order_date, base_lead, shutdowns):
    """Lead time for an order placed on order_date, including any shutdown it runs into."""
    lead = base_lead
    for _, start, end, extra in shutdowns:
        if order_date <= end and order_date + timedelta(days=lead) >= start:
            lead += extra
    return lead


def number(row, col, line, default=None):
    raw = (row.get(col) or "").strip()
    if raw == "" and default is not None:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        sys.exit(f"Line {line} ({row.get('sku') or 'no sku'}): {col} must be a number, got {raw!r}")
    if value < 0:
        sys.exit(f"Line {line} ({row.get('sku') or 'no sku'}): {col} can't be negative")
    return value


def plan_row(row, line, today, safety_days, cover_days, warnings=None):
    on_hand = number(row, "on_hand", line)
    on_order = number(row, "on_order", line, default=0)
    daily = number(row, "sold_last_30d", line) / 30
    base_lead = math.ceil(number(row, "lead_time_days", line))
    origin = (row.get("origin") or "").strip().lower()
    shutdowns = [] if origin in NOT_CHINA else CHINA_SHUTDOWNS
    known_china = origin in ("", "cn", "hk") or "china" in origin or "hong kong" in origin
    if origin not in NOT_CHINA and not known_china:
        if warnings is not None:
            warnings.append(f"Line {line} ({row.get('sku') or 'no sku'}): origin {row['origin'].strip()!r} "
                            "isn't recognised, so China holidays were applied. Use China, UK or EU.")

    if daily == 0:
        return dict(row, on_hand=f"{on_hand:g}", on_order=f"{on_order:g}", daily="0.0", stockout="never",
                    order_by="-", lead="-", order_qty=0, status="NO SALES")

    # stockout: when the shelf is empty, ignoring stock on order.
    # covered_until: when you'd run out counting stock on order, as if it lands in time.
    # The next order is planned from covered_until, so stock already ordered isn't ordered twice.
    stockout = today + timedelta(days=math.floor(on_hand / daily))
    position = on_hand + on_order
    covered_until = today + timedelta(days=math.floor(position / daily))

    # Latest order date whose (shutdown-adjusted) delivery still lands `safety_days` before that.
    order_by = covered_until - timedelta(days=base_lead + safety_days)
    while order_by > today - timedelta(days=365) and (
        order_by + timedelta(days=effective_lead_time(order_by, base_lead, shutdowns) + safety_days) > covered_until
    ):
        order_by -= timedelta(days=1)

    # Order enough to last until the *next* order (placed ~cover_days from now) lands, plus the
    # safety buffer. If that next order runs into a shutdown, this one has to carry you through
    # it: this is what stops you running dry over Chinese New Year.
    lead_next = effective_lead_time(today + timedelta(days=cover_days), base_lead, shutdowns)
    order_qty = max(0, math.ceil(daily * (cover_days + lead_next + safety_days) - position))

    if order_by < today:
        status = "LATE - ORDER NOW"
    elif order_by <= today + timedelta(days=7):
        status = "ORDER THIS WEEK"
    else:
        status = "OK"

    return dict(
        row,
        on_hand=f"{on_hand:g}",
        on_order=f"{on_order:g}",
        daily=f"{daily:.1f}",
        stockout=stockout.isoformat(),
        order_by=order_by.isoformat(),
        lead=effective_lead_time(today, base_lead, shutdowns),
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

    # utf-8-sig: Excel's "CSV UTF-8" puts an invisible marker at the start of the file.
    # cp1252: Excel's plain "CSV" on Windows, e.g. for a name like "Crème brûlée". latin-1 never fails.
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(args.csv_path, newline="", encoding=encoding) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    reader = csv.DictReader(io.StringIO(text, newline=""))
    missing = {"sku", "name", "on_hand", "sold_last_30d", "lead_time_days"} - set(reader.fieldnames or [])
    if missing:
        sys.exit(f"{args.csv_path} is missing column(s): {', '.join(sorted(missing))}")
    warnings = []
    rows = [plan_row(r, reader.line_num, args.today, args.safety_days, args.cover_days, warnings)
            for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]

    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], r["order_by"]))

    cols = [("status", 16), ("sku", 14), ("name", 24), ("on_hand", 7), ("on_order", 8), ("daily", 6),
            ("stockout", 10), ("order_by", 10), ("lead", 5), ("order_qty", 9)]
    print("  ".join(h.upper().ljust(w) for h, w in cols))
    for r in rows:
        print("  ".join(" ".join(str(r[h]).split())[:w].ljust(w) for h, w in cols))

    for w in warnings:
        print(f"\nWARNING: {w}")
    upcoming = [s for s in CHINA_SHUTDOWNS if s[2] >= args.today]
    if upcoming:
        name, start, end, _ = upcoming[0]
        print(f"\nNext China shutdown: {name}, {start:%d %b} - {end:%d %b %Y}.")
    if CHINA_SHUTDOWNS[-1][2] < args.today + timedelta(days=180):
        print(f"\nWARNING: shutdown dates in tools/reorder.py stop at {CHINA_SHUTDOWNS[-1][2]:%d %b %Y}. "
              "Add next year's Golden Week and Chinese New Year to CHINA_SHUTDOWNS.")


if __name__ == "__main__":
    main()
