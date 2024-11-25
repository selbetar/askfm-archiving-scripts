from __future__ import annotations

import contextlib
import hmac
import itertools
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Union
from urllib.parse import quote

from requests import Session

from . import requests as _r
from .errors import AskfmApiError, OperationError, RequestError, SessionError

# === Defaults ===
DEFAULT_HEADERS = {
    "Accept": "application/json; charset=utf-8",
    "Accept-Encoding": "identity",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 6.0.1; GT-N7100 Build/MOB30R)",
    "X-Api-Version": "1.18",
    "X-Client-Type": "android_4.90.7",
}
DEFAULT_HOST = "api.ask.fm:443"
DEFAULT_LIMIT = 50

# === Types ===
ReqParams = dict[str, Any]
StrParams = dict[str, str]
Response = Any
Auth = tuple[str, str]  # login, password


@dataclass
class Request:
    method: str
    path: str
    params: ReqParams = field(default_factory=dict)
    name: Optional[str] = None
    unwrap_key: Optional[str] = None
    paginated: bool = False
    item_id_key: Optional[str] = None


class AskfmApi:
    api_key: bytes
    auto_refresh_session: bool
    device_id: str
    auth: Optional[Auth]
    headers: dict[str, str]

    logged_in: bool = False
    sess: Session
    rt: str = "1"

    _access_token: Optional[str] = None
    _host: str

    @classmethod
    def random_device_id(cls):
        return secrets.token_hex(8)

    def __init__(
        self,
        api_key: Union[str, bytes],
        *,
        auto_refresh_session: bool = True,
        device_id: Optional[str] = None,
        access_token: Optional[str] = None,
        logged_in: bool = False,
        auth: Optional[Auth] = None,
        host: str = DEFAULT_HOST,
        headers: dict[str, str] = DEFAULT_HEADERS,
    ) -> None:
        if isinstance(api_key, str):
            api_key = bytes(api_key, encoding="ascii")
        self.api_key = api_key
        self.auto_refresh_session = auto_refresh_session
        self.device_id = device_id or AskfmApi.random_device_id()
        self.auth = auth

        self.sess = Session()
        self.sess.headers.update(headers)
        self.host = host

        if access_token is not None:
            self.access_token = access_token
            self.logged_in = logged_in
            # In theory, we could detect this automatically.
            # Seems that authenticated tokens start with ".3" and anon tokens with ".5".
        elif logged_in:
            raise TypeError("passed `logged_in` without `access_token`")
        elif auto_refresh_session:
            self.refresh_session()

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    @access_token.setter
    def access_token(self, token: Optional[str]) -> None:
        self._access_token = token
        self.sess.headers["X-Access-Token"] = token  # type: ignore

    @property
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, host: str) -> None:
        self._host = host
        self.sess.headers["Host"] = host

    def log_in(self, username: str, password: str) -> Response:
        return self.refresh_session((username, password))

    def refresh_session(self, auth: Optional[Auth] = None) -> Optional[Response]:
        with self.disable_auto_refresh():  # guard against recursive refreshes
            # get initial anon token
            self.access_token = self.request(_r.get_access_token(self.device_id))
            self.logged_in = False
            if auth := (auth or self.auth):
                # get user token
                res = self.request(_r.log_in(auth[0], auth[1], self.device_id))
                self.access_token = res["accessToken"]
                self.logged_in = True
                return res["user"]
        return None

    def check_session(self) -> bool:
        with self.disable_auto_refresh():
            with contextlib.suppress(RequestError, OperationError):
                self.request(_r.fetch_my_profile())
                self.logged_in = True
                return True
            self.logged_in = False
            self.access_token = None
            return False

    @contextlib.contextmanager
    def disable_auto_refresh(self):
        old_val = self.auto_refresh_session
        self.auto_refresh_session = False
        try:
            yield
        finally:
            self.auto_refresh_session = old_val

    def request(
        self,
        req: Request,
        *,
        unwrap: bool = True,
        offset: int = 0,
        from_ts: int = None,
        limit: int = DEFAULT_LIMIT,
    ) -> Response:
        if not self.access_token and self.auto_refresh_session:
            self.refresh_session()

        if req.paginated:
            if from_ts is None:
                params = {"offset": offset, "limit": limit, **req.params}
            else:
                params = {"limit": limit, **req.params}
                params["from"] = (
                    from_ts  # req.params could have `from` and end up overriding the iterator value
                )
        else:
            params = req.params

        for i in itertools.count():
            res = self.request_raw(req.method, req.path, params)
            if "error" not in res:
                break
            error = AskfmApiError.from_response(res)
            if not self.handle_error(error, req, i):
                raise error

        if unwrap and req.unwrap_key:
            res = res[req.unwrap_key]
        return res

    def handle_error(self, error: AskfmApiError, req: Request, attempt_no: int) -> bool:
        """Invalidate/refresh the session and return whether we should retry the request."""
        if isinstance(error, SessionError):
            self.logged_in = False
            self.access_token = None
            if attempt_no == 1 and self.auto_refresh_session:
                self.refresh_session()
                return True
        return False

    def request_iter(
        self,
        req: Request,
        *,
        offset: int = 0,
        from_ts: int = None,
        page_limit: int = DEFAULT_LIMIT,
    ) -> Iterator[Response]:
        if not req.paginated or not req.unwrap_key:
            raise TypeError("Cannot iterate non-paginated request")

        while True:
            res = self.request(
                req, from_ts=from_ts, offset=offset, limit=page_limit, unwrap=False
            )
            items = res[req.unwrap_key]
            if not items:  # strangely, API always returns hasMore=True
                break

            yield from items
            # if not res.get("incomplete", False) and not res["hasMore"]:
            #     break
            offset += len(items)
            prev_ts = from_ts
            from_ts = items[-1].get("ts")

            if prev_ts is not None and prev_ts == from_ts:
                break

    def request_raw(
        self, method: str, path: str, params: Optional[ReqParams] = None
    ) -> Response:
        params = params or {}
        method = method.upper()
        has_body = method in ["POST", "PUT"]
        url = "https://" + self.host + path

        params = {"rt": self.rt, "ts": int(time.time()), **params}
        params = self.normalize_params(params)
        if has_body:
            params = {"json": json.dumps(params, sort_keys=True, separators=(",", ":"))}
        signature = f"HMAC {self.get_signature(method, path, params)}"

        res = self.sess.request(
            method,
            url,
            data=params if has_body else None,
            params=params if not has_body else None,
            headers={"Authorization": signature},
        )

        if "X-Next-Token" in res.headers:
            self.rt = res.headers["X-Next-Token"]

        return res.json()

    def normalize_params(self, params: ReqParams) -> ReqParams:
        result = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, (int, bool)):
                v = str(v).lower()
            result[k] = v
        return result

    def get_signature(self, method: str, path: str, params: StrParams) -> str:
        quoted = [key + "%" + quote(val, safe="!'()~") for (key, val) in params.items()]
        msg = "%".join(sorted(quoted))
        msg = "%".join([method.upper(), self.host, path, msg])

        hmac_ = hmac.new(self.api_key, msg.encode(), "sha1")
        return hmac_.hexdigest()
