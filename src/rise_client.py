"""RiseAPI client"""

import json
import random
from contextlib import suppress
from dataclasses import asdict, dataclass
from functools import cache, cached_property
from typing import Literal, NewType, TypedDict, cast

import requests
from eth_typing.encoding import HexStr
from requests.exceptions import JSONDecodeError
from requests.models import HTTPError, Response

from . import log
from .frame_signer import FrameSigner

USDC_DECIMALS = 6


USDCInWei = NewType("USDCInWei", int)


RiseId = NewType("RiseId", str)


@dataclass
class Payment:
    """Payment dataclass"""

    recipient: RiseId
    amount: USDCInWei

    salt: int | None = None

    def __post_init__(self):
        self.salt = random.getrandbits(32)

    @property
    def usd_amount(self) -> float:
        """Return amount in USD"""
        return self.amount / 10**USDC_DECIMALS


TeamId = NewType("TeamId", str)


class Team(TypedDict):
    """Team enitity"""

    id: TeamId
    name: str
    riseId: RiseId


MemberId = NewType("MemberId", str)


class TeamMember(TypedDict):
    """Team member entity"""

    id: MemberId
    alias: str
    firstname: str
    middlename: str
    lastname: str
    riseId: RiseId


class RiseAPI:
    """Rise API client"""

    # API_BASE = "https://api.riseworks.io/v1"
    API_BASE = "https://staging-b2b-api.riseworks.io/v1"

    AUTH_ENDPOINT = API_BASE + "/auth/api/siwe"
    TEAM_ENDPOINT = API_BASE + "/teams/"  # doesn't work without trailing slash
    PAYMNET_ENDPOINT = API_BASE + "/payments"

    signer: FrameSigner
    rise_id: RiseId
    token: str

    def __init__(self, rise_id: RiseId, signer: FrameSigner):
        self.rise_id = rise_id
        self.signer = signer
        self._auth()

    @cached_property
    def allowed_recipients(self) -> list[RiseId]:
        """Return a list of allowed recipients"""
        return [p["riseId"] for p in self.payees]

    @cache
    def get_payee(self, rise_id: RiseId) -> TeamMember:
        """Return a payee by rise id"""
        for payee in self.payees:
            if payee["riseId"] == rise_id:
                return payee
        raise ValueError(f"Payee with rise id {rise_id} not found")

    @cached_property
    def payees(self) -> list[TeamMember]:
        """Return a list of payees"""
        payees = []
        for team in self.get_teams():
            payees.extend(self.get_team_members(team["id"]))
        return payees

    def get_teams(self) -> list[Team]:
        """Return a list of teams"""
        return cast(list[Team], self._request("GET", self.TEAM_ENDPOINT))

    def get_team_members(self, team_id: TeamId) -> list[TeamMember]:
        """Return a list of team members"""
        return cast(
            list[TeamMember],
            self._request(
                "GET", f"{self.TEAM_ENDPOINT}/{team_id}/talent"
            ),  # NOTE: 404 returns html
        )

    def batch_payment(self, payments: list[Payment]) -> None:
        """Execute batch payment"""
        request = self._get_batch_payment_message(payments)  # TODO: dataclass for the return type
        log.info("Sign transaction to send batch payment")
        signature = self.signer.sign_typed(request)
        self._send_batch_payment(payments, request["message"], signature)

    def _get_batch_payment_message(self, payments: list[Payment]) -> dict:
        """Create batch payment request"""
        return self._request(
            "PUT",
            f"{self.PAYMNET_ENDPOINT}/batch-pay",
            json={
                "wallet": self.signer.account,
                "rise_id": self.rise_id,
                # TODO: the following two fields may be constructed by the method
                "total_amount": str(sum(p.amount for p in payments)),
                "payments": [asdict(p) for p in payments],
            },
        )

    def _send_batch_payment(
        self, payments: list[Payment], request: dict, signature: HexStr
    ) -> None:
        """Execute batch payment request"""
        self._request(
            "POST",
            f"{self.PAYMNET_ENDPOINT}/batch-pay",
            json={
                "wallet": self.signer.account,
                "rise_id": self.rise_id,
                "total_amount": str(sum(p.amount for p in payments)),
                "payments": [asdict(p) for p in payments],
                "request": request,
                "signature": signature,
            },
        )

    def _auth(self):
        """Authenticate with Rise API"""
        msg = self._get_sign_message()
        log.info("Sign message to sign in")
        sig = self.signer.sign(msg)
        self.token = self._get_token(msg, sig)

    def _get_sign_message(self) -> str:
        """Return message to be signed"""
        data = self._request(
            "GET",
            self.AUTH_ENDPOINT,
            auth=False,
            params={"wallet": self.signer.account},
        )
        return data["message"]

    def _get_token(self, signed_msg: str, signature: str) -> str:
        """Return bearer token"""
        data = self._request(
            "POST",
            self.AUTH_ENDPOINT,
            auth=False,
            json={
                "wallet": self.signer.account,
                "message": signed_msg,
                "signature": signature,
            },
        )
        return data["token"]

    def _request(
        self,
        method: Literal["GET", "POST", "PUT"],
        endpoint: str,
        auth: bool = True,
        **kwargs,
    ) -> dict:
        func = getattr(requests, method.lower(), None)
        if func is None:
            raise ValueError(f"Unknown method: {method}")

        headers = kwargs.get("headers", {})
        if "headers" in kwargs:
            del kwargs["headers"]

        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"

        if auth:
            headers.update(self._auth_headers())

        resp = func(endpoint, headers=headers, **kwargs)
        self._raise_for_status(resp, f"Unable to {method} {endpoint}")

        try:
            return resp.json()["data"]
        except JSONDecodeError as ex:
            raise RuntimeError(f"Unable to decode response: {resp.text}") from ex
        except KeyError as ex:
            raise RuntimeError(
                f"Unable to find `data` field in response: {json.dumps(resp.json(), indent=4)}"
            ) from ex

    def _auth_headers(self) -> dict:
        """Return auth headers"""
        return {"Authorization": f"Bearer {self.token}"}

    def _raise_for_status(self, response: Response, msg: str) -> None:
        """Format error message"""
        try:
            response.raise_for_status()
        except HTTPError as ex:
            with suppress(JSONDecodeError, KeyError):
                error = response.json()["message"]
                msg = f"{msg}: {error}"
            raise RuntimeError(msg) from ex
