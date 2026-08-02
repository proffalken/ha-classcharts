from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import unquote
from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

# The JSON API login endpoint (apiv2parent/login) returns a session_id but
# never issues a session cookie, so every subsequent data call gets silently
# redirected through session.tes.com's verification gate and comes back
# "successful" but empty. The real HTML login form does establish a verified
# session, so that's what we authenticate against instead.
LOGIN_URL = "https://www.classcharts.com/parent/login"
PING_URL = "https://www.classcharts.com/apiv2parent/ping"
SITE_URL = "https://www.classcharts.com/"
PUPILS_URL = "https://www.classcharts.com/apiv2parent/pupils"
BEHAVIOUR_URL_TMPL = "https://www.classcharts.com/apiv2parent/behaviour/{student_id}"
TIMETABLE_URL_TMPL = "https://www.classcharts.com/apiv2parent/timetable/{student_id}"

REQUEST_TIMEOUT = ClientTimeout(total=30)

class ClassChartsError(Exception):
    pass

class AuthError(ClassChartsError):
    pass

class ClassChartsClient:
    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._session_id: Optional[str] = None
        self._auth_header: Dict[str, str] = {}
        self._login_lock = asyncio.Lock()

    async def login(self) -> None:
        """Force a fresh login, serialised so concurrent callers share one HTTP request."""
        async with self._login_lock:
            await self._do_login()

    async def _do_login(self) -> None:
        payload = (
            f"_method=POST&email={self._email}&logintype=existing"
            f"&password={self._password}&recaptcha-token=no-token-available"
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with self._session.post(
                LOGIN_URL, data=payload, headers=headers, timeout=REQUEST_TIMEOUT
            ):
                pass
        except (ClientError, TimeoutError) as e:
            raise ClassChartsError(str(e)) from e

        token = self._extract_session_token()
        if not token:
            _LOGGER.debug("ClassCharts login: no session cookie found after login POST")
            raise AuthError("Login failed")

        self._session_id = token
        self._auth_header = {
            "Authorization": f"Basic {token}",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.classcharts.com/mobile/parent",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        await self._ping()

    def _extract_session_token(self) -> Optional[str]:
        cookies = self._session.cookie_jar.filter_cookies(SITE_URL)

        raw = cookies.get("parent_session_credentials")
        if raw is not None:
            try:
                decoded = json.loads(unquote(raw.value))
                token = decoded.get("session_id")
                if token:
                    return token
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        cc = cookies.get("cc-session")
        return cc.value if cc is not None else None

    async def _ping(self) -> None:
        """Activate the session -- data endpoints return empty results without this."""
        try:
            async with self._session.post(
                PING_URL, data="{}", headers=self._auth_header, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    raise AuthError(f"Session activation failed: status={resp.status}")
        except (ClientError, TimeoutError) as e:
            raise ClassChartsError(str(e)) from e

    async def _request(
        self, method: str, url: str, data: Any = None, params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        headers = dict(self._auth_header)
        try:
            async with self._session.request(
                method, url, headers=headers, timeout=REQUEST_TIMEOUT, data=data, params=params
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status == 401:
                    raise AuthError("Unauthorised")
                if body is None or "success" not in body:
                    raise ClassChartsError(f"Unexpected response: {body}")
                return body
        except (ClientError, TimeoutError, ValueError) as e:
            raise ClassChartsError(str(e)) from e

    async def ensure_auth(self) -> None:
        if self._session_id:
            return
        async with self._login_lock:
            if self._session_id:
                return
            await self._do_login()

    async def pupils(self) -> List[Dict[str, Any]]:
        await self.ensure_auth()
        data = await self._request("POST", PUPILS_URL, data="{}")
        pupils = data.get("data", [])
        if not pupils:
            _LOGGER.debug("ClassCharts pupils response was empty: %s", data)
        return pupils

    async def behaviour(self, student_id: int) -> Dict[str, Any]:
        await self.ensure_auth()
        url = BEHAVIOUR_URL_TMPL.format(student_id=student_id)
        try:
            return await self._request("GET", url)
        except AuthError:
            await self.login()
            return await self._request("GET", url)

    async def timetable(self, student_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        await self.ensure_auth()
        url = TIMETABLE_URL_TMPL.format(student_id=student_id)
        params = {"date": date} if date else None
        try:
            return await self._request("GET", url, params=params)
        except AuthError:
            await self.login()
            return await self._request("GET", url, params=params)
