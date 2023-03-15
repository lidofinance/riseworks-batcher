"""Read payments from csv file"""

import csv
import re
import sys
from typing import Literal, NewType, TypedDict, cast

from . import log
from .rise_client import USDC_DECIMALS, Payment, RiseId, USDCInWei

DAIInUsd = NewType("DAIInUsd", str)


class CSVRow(TypedDict):
    """Row of the csv file"""

    outgoing_amount: DAIInUsd
    outgoing_token: Literal["DAI"]
    Description: str  # pylint: disable=invalid-name


def payments_from_csv(path: str) -> list[Payment]:
    """Read payments from csv file"""
    with open(path, encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter=",")
        rows = cast(tuple[CSVRow], tuple(row for row in reader))

    payments = []

    for row in rows:
        _sanity_checks(row)
        payments.append(
            Payment(
                amount=payment_amount(row["outgoing_amount"]),
                recipient=find_rise_id(row["Description"]),
            )
        )

    return payments


def find_rise_id(text: str) -> RiseId:
    """RiseId of the recipient"""
    is_address = re.compile(r"0x[0-9a-fA-F]{40}")
    matches = is_address.findall(text)

    if not matches:
        log.error(f"RiseId not found in [bold]{text}[/bold]")
        sys.exit(1)
    if len(matches) > 1:
        log.error(f"Multiple RiseIds found in [bold]{text}[/bold]")
        sys.exit(1)

    return RiseId(matches.pop())


def payment_amount(amount: DAIInUsd) -> USDCInWei:
    """Convert DAI to USDC in Wei"""
    try:
        _float_amount = float(amount)
    except ValueError:
        log.error(f"Invalid amount: [bold]{amount}[/bold]")
        sys.exit(1)

    return USDCInWei(int(_float_amount * 10**USDC_DECIMALS))


def _sanity_checks(row: CSVRow) -> None:
    if row["outgoing_token"] != "DAI":
        log.error(f"Unsupported token: [bold]{row['outgoing_token']}[/bold]")
        sys.exit(1)
