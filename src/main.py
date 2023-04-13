"""
Main module.
    Usage: ENTITY_RISE_ID=0x0000 python -m src.main <payments.csv>
"""

import os
import sys
from typing import TypedDict

from rich.table import Table
from rich.tree import Tree

from . import log
from .datasource import payments_from_csv
from .frame_signer import FrameSigner
from .rise_client import RiseAPI, RiseId


class Config(TypedDict):
    """Configuration of the script"""

    ENTITY_RISE_ID: RiseId


def read_envs() -> Config:
    """Read environment variables to Config object"""
    config_ = os.environ.copy()

    for key in config_.copy():
        if key not in Config.__annotations__:
            del config_[key]

    res: dict = {}
    for key, type_ in Config.__annotations__.items():  # type: ignore
        if key not in config_:
            raise RuntimeError(f"Required variable={key} not found")
        res[key] = type_(config_[key])

    return Config(**res)  # type: ignore


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log.error("Usage: python -m src.main <payments.csv>")
        sys.exit(1)

    filename = sys.argv[1]  # pylint: disable=invalid-name
    if not os.path.exists(filename):
        log.error(f"File {filename} does not exist")
        sys.exit(1)

    config = read_envs()
    entity = config["ENTITY_RISE_ID"]

    log.info(f"Connecting to the entity with RiseId [magenta]{entity}")

    signer = FrameSigner()
    api = RiseAPI(entity, signer)
    log.info(f"Using payments file [magenta]{filename}")
    payments = payments_from_csv(filename)

    tree = Tree(entity, style="bold green")

    for i, p in enumerate(payments):
        if p.recipient not in api.allowed_recipients:
            raise RuntimeError(f"Recipient {p.recipient} is not a payee")
        payee = api.get_payee(p.recipient)

        table = Table()
        table.add_column("#", style="dim")
        table.add_column("RiseId", style="cyan")
        table.add_column("Full name")
        table.add_column("Amount", justify="right", style="yellow")

        table.add_row(
            str(i + 1),
            str(p.recipient),
            f"{payee['firstname']} {payee['lastname']}",
            f"{(p.usd_amount):,.2f} $",
        )

        log.console.print(table)
        if not log.prompt_yes_no("Confirm payment?"):
            log.error("Payment cancelled by user")
            sys.exit(1)

        tree.add(f"[dim]{i + 1}[/dim] {p.recipient} <- [yellow]{p.usd_amount:.2f} $")

    log.warn("Check the batch summary:")
    log.console.print(tree)
    log.info(f"Total amount: [yellow]{sum(p.usd_amount for p in payments):,.2f} $")

    if not log.prompt_yes_no("Confirm payment?"):
        log.error("Payment cancelled by user")
        sys.exit(1)

    api.batch_payment(payments)

    link = f"https://arbiscan.io/address/{entity.lower()}#tokentxns"
    log.info(f"Check explorer for the transaction: [link={link}]{link}[/link]")

    log.okay("Done!")
