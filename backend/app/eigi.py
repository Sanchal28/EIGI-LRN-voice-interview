import httpx
from fastapi import HTTPException, status
from urllib.parse import urlsplit, urlunsplit

from app.schemas import StartInterviewRequest
from app.settings import Settings


class EigiService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def api_base_url(self) -> str:
        configured = self.settings.eigi_base_url.strip().rstrip("/")
        parsed = urlsplit(configured)
        scheme = parsed.scheme or "https"
        host = parsed.netloc or parsed.path
        path = parsed.path if parsed.netloc else ""
        if host.lower() in {"eigi.ai", "www.eigi.ai", "api.eigi.ai"}:
            return urlunsplit(("https", "api.eigi.ai", "/v1", "", ""))
        if "/v1" in path:
            path = f"{path.split('/v1', 1)[0]}/v1"
        elif not path or path == "/":
            path = "/v1"
        return urlunsplit((scheme, host, path.rstrip("/"), "", ""))

    @staticmethod
    def _find_prompt_access_token(value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("prompt_access_token", "promptAccessToken", "access_token", "accessToken"):
                token = value.get(key)
                if isinstance(token, str) and token.strip():
                    return token.strip()
            for nested in value.values():
                token = EigiService._find_prompt_access_token(nested)
                if token:
                    return token
        if isinstance(value, list):
            for nested in value:
                token = EigiService._find_prompt_access_token(nested)
                if token:
                    return token
        return ""

    async def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.request(
                    method,
                    f"{self.api_base_url}{path}",
                    headers={"X-API-Key": self.settings.eigi_api_key},
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Voice provider timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Voice provider rejected the request ({exc.response.status_code}).",
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Voice provider is unavailable.") from exc
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="Voice provider returned an invalid response.")
        return data

    async def create_session(self, request: StartInterviewRequest, attempt_id: str) -> dict:
        if not self.settings.eigi_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice interviews are not configured yet.",
            )

        variables = {
            "interview_attempt_id": attempt_id,
            "target_role": request.target_role,
            "focus_area": request.focus_area,
            "interview_mode": request.interview_mode,
            "duration_minutes": request.duration_minutes,
            "resume_context": request.resume_context,
        }
        agent = await self._request("GET", f"/public/agents/{self.settings.eigi_agent_id}")
        prompt_access_token = self._find_prompt_access_token(agent)
        if not prompt_access_token:
            raise HTTPException(status_code=502, detail="Voice is not enabled for this Eigi agent.")

        payload = {
            "agent_id": self.settings.eigi_agent_id,
            "prompt_access_token": prompt_access_token,
            "conversation_config_type": "VOICE",
            "conversation_metadata": {
                "agent_id": self.settings.eigi_agent_id,
                "interview_attempt_id": attempt_id,
                **variables,
                "dynamic_variables": variables,
                "source_app": "lrn",
            },
        }
        data = await self._request("POST", "/widgets/sessions/daily", payload=payload)

        required = {"conversation_id", "dailyRoom", "dailyToken"}
        if not isinstance(data, dict) or not required.issubset(data):
            raise HTTPException(status_code=502, detail="Voice provider returned an invalid session.")
        return data

    async def get_conversation(self, conversation_id: str) -> dict:
        return await self._request("GET", f"/public/conversations/{conversation_id}")

