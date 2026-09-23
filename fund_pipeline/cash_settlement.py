"""Part 4: separate settled GBP cash from outstanding trade obligations."""

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fund_pipeline.build_positions import build_positions, read_events, positive_quantity
from fund_pipeline.daily_close import pounds
from fund_pipeline.landing import verify_delivery


def cash_amount(value):
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid cash amount: {value}") from error
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise ValueError(f"Cash amount must be finite and in whole pennies: {value}")
    return amount


def calculate_cash(folder, business_date, as_of, currency="GBP"):
    if currency not in ("GBP", "USD"):
        raise ValueError("Supported single-currency examples are GBP and USD")
    trade_date = date.fromisoformat(business_date)
    close_date = date.fromisoformat(as_of)
    if close_date < trade_date:
        raise ValueError("As-of date cannot precede the trade date")

    # Reuse the existing quantity and allocation controls before calculating cash.
    position_result = build_positions(folder, business_date)
    executions, _ = read_events(
        folder / "executions.csv",
        ["business_date", "execution_id", "instrument", "side", "quantity"],
        "execution_id", business_date,
    )
    terms, _ = read_events(
        folder / "execution_terms.csv",
        ["business_date", "execution_id", "currency", "execution_price", "settlement_due"],
        "execution_id", business_date,
    )
    confirmations, repeated_settlements = read_events(
        folder / "settlements.csv",
        ["business_date", "settlement_id", "execution_id", "currency", "amount", "settled_on"],
        "settlement_id", business_date,
    )
    opening, repeats = read_events(
        folder / "opening_cash.csv", ["business_date", "currency", "balance"],
        "currency", business_date,
    )
    if set(opening) != {currency} or repeats:
        raise ValueError(f"Expected exactly one {currency} opening cash record")
    if set(terms) != set(executions):
        raise ValueError("Execution terms must match the execution IDs exactly")

    amounts = {}
    due_dates = {}
    for execution_id, execution in executions.items():
        term = terms[execution_id]
        if term["currency"] != currency:
            raise ValueError(f"Expected {currency} execution terms")
        price = positive_quantity(term["execution_price"])
        amounts[execution_id] = cash_amount(positive_quantity(execution["quantity"]) * price)
        due_dates[execution_id] = date.fromisoformat(term["settlement_due"])
        if due_dates[execution_id] < trade_date:
            raise ValueError("Settlement due date cannot precede the trade date")

    settled_dates = {}
    for confirmation in confirmations.values():
        execution_id = confirmation["execution_id"]
        if execution_id not in executions:
            raise ValueError(f"Settlement references unknown execution {execution_id}")
        if execution_id in settled_dates:
            raise ValueError(f"Multiple settlement confirmations for {execution_id}")
        if confirmation["currency"] != currency:
            raise ValueError(f"Expected {currency} settlement confirmations")
        if cash_amount(confirmation["amount"]) != amounts[execution_id]:
            raise ValueError(f"Settlement amount mismatch for {execution_id}")
        settled_on = date.fromisoformat(confirmation["settled_on"])
        if settled_on < trade_date:
            raise ValueError("Actual settlement date cannot precede the trade date")
        settled_dates[execution_id] = settled_on

    cash = cash_amount(opening[currency]["balance"])
    receivables = Decimal("0")
    payables = Decimal("0")
    obligations = []
    for execution_id, execution in executions.items():
        amount = amounts[execution_id]
        is_buy = execution["side"] == "BUY"
        settled_on = settled_dates.get(execution_id)
        if settled_on is not None and settled_on <= close_date:
            cash += -amount if is_buy else amount
        else:
            if is_buy:
                payables += amount
            else:
                receivables += amount
            obligations.append({
                "execution_id": execution_id,
                "type": "PAYABLE" if is_buy else "RECEIVABLE",
                "amount": amount,
                "due": due_dates[execution_id].isoformat(),
                "status": "OVERDUE" if due_dates[execution_id] <= close_date else "OPEN",
            })

    return {
        "currency": currency,
        "positions": position_result["positions"],
        "cash": cash,
        "receivables": receivables,
        "payables": payables,
        "net_cash_and_obligations": cash + receivables - payables,
        "obligations": obligations,
        "repeated_settlements": repeated_settlements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", required=True, type=date.fromisoformat)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--delivery", required=True, type=Path)
    parser.add_argument("--currency", choices=("GBP", "USD"), default="GBP")
    args = parser.parse_args()
    business_date = args.business_date.isoformat()
    as_of = args.as_of.isoformat()
    manifest = verify_delivery(args.delivery, business_date, bundle="settlement")
    result = calculate_cash(args.delivery, business_date, as_of, args.currency)
    print(f"Input delivery: {manifest['delivery_id']}")
    print(f"Cash as of {as_of} | trade batch {business_date} | {args.currency} | NOT APPROVED")
    print(f"Settled cash: {pounds(result['cash'])}")
    print(f"Receivables (owed to us): {pounds(result['receivables'])}")
    print(f"Payables (we owe): {pounds(result['payables'])}")
    print(f"Cash + receivables - payables: {pounds(result['net_cash_and_obligations'])}")
    for obligation in result["obligations"]:
        print(f"{obligation['execution_id']}: {obligation['type']} "
              f"{pounds(obligation['amount'])}, due {obligation['due']}, {obligation['status']}")
    print(f"Repeated settlement records ignored: {result['repeated_settlements']}")
    print("This subtotal excludes share values; it is not NAV or available buying power.")


if __name__ == "__main__":
    main()
