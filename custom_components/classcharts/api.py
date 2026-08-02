from __future__ import annotations
from typing import Any, Dict, List, Optional
from aiohttp import ClientSession, ClientError

LOGIN_URL = "https://www.classcharts.com/apiv2parent/login"
PUPILS_URL = "https://www.classcharts.com/apiv2parent/pupils"
BEHAVIOUR_URL_TMPL = "https://www.classcharts.com/apiv2parent/behaviour/{student_id}"
TIMETABLE_URL_TMPL = "https://www.classcharts.com/apiv2parent/timetable/{student_id}"

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

    async def login(self) -> None:
        payload = f"email={self._email}&password={self._password}&remember=true&recaptcha-token=no-token-available"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with self._session.post(LOGIN_URL, data=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            sid = (data or {}).get("meta", {}).get("session_id")
            if resp.status != 200 or not sid:
                raise AuthError("Login failed")
            self._session_id = sid
            self._auth_header = {"Authorization": f"Basic {sid}"}

    async def _request(self, method: str, url: str) -> Dict[str, Any]:
        headers = dict(self._auth_header)
        try:
            async with self._session.request(method, url, headers=headers) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 401:
                    raise AuthError("Unauthorised")
                if data is None or "success" not in data:
                    raise ClassChartsError(f"Unexpected response: {data}")
                return data
        except ClientError as e:
            raise ClassChartsError(str(e)) from e

    async def ensure_auth(self):
        if not self._session_id:
            await self.login()

    async def pupils(self) -> List[Dict[str, Any]]:
        await self.ensure_auth()
        data = await self._request("GET", PUPILS_URL)
        return data.get("data", [])

    async def behaviour(self, student_id: int) -> Dict[str, Any]:
        await self.ensure_auth()
        url = BEHAVIOUR_URL_TMPL.format(student_id=student_id)
        try:
            return await self._request("GET", url)
        except AuthError:
            await self.login()
            return await self._request("GET", url)

    async def timetable_today(self, student_id: int) -> Dict[str, Any]:
        await self.ensure_auth()
        url = TIMETABLE_URL_TMPL.format(student_id=student_id)
        try:
            return await self._request("GET", url)
        except AuthError:
            await self.login()
            return await self._request("GET", url)

