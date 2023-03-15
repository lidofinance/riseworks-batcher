"""Signer using frame.sh"""

import sys
from functools import cached_property

from eth_typing.encoding import HexStr
from eth_typing.evm import ChecksumAddress
from eth_utils.conversions import to_hex
from web3 import HTTPProvider, Web3

from . import log


class FrameSigner:
    """Wallet signer using frame.sh"""

    # TODO: set chain id or check?
    # TODO: token cache?

    FRAME_URI = "http://localhost:1248"

    w3: Web3

    def __init__(self, timeout_s: int = 300):
        self.w3 = self._establish_conn_to_frame(timeout_s)

    @cached_property
    def account(self) -> ChecksumAddress:
        """Return account address"""
        if self.w3.eth.accounts:
            return self.w3.eth.accounts[0]
        log.error("Expected account to be unlocked")
        sys.exit(1)

    def sign(self, msg: str) -> HexStr:
        """Basic message signature"""
        try:
            sig = self.w3.eth.sign(self.account, text=msg)
        except ValueError as ex:
            log.error(f"Error signing message: {ex}")
            sys.exit(1)

        return to_hex(sig)

    def sign_typed(self, msg: dict) -> HexStr:
        """Signature of EIP712 typed data"""
        try:
            return self.w3.manager.request_blocking(
                "eth_signTypedData_v4", [self.account, msg]  # type: ignore
            )
        except ValueError as ex:
            log.error(f"Error signing message: {ex}")
            sys.exit(1)

    def _establish_conn_to_frame(self, timeout_s: int) -> Web3:
        """Check that frame connection is established"""
        p = HTTPProvider(self.FRAME_URI, {"timeout": timeout_s})
        if not p.isConnected():
            log.warn("Frame connection is not established")
            if log.prompt_yes_no("Retry?"):
                return self._establish_conn_to_frame(timeout_s)
            log.warn("Script aborted")
            sys.exit(1)
        return Web3(p)
