import requests
import logging
import allure

logger = logging.getLogger("qa_test")


class ApiClient:
    """QA 平台 API 客户端封装"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.token = None

    def set_token(self, token: str):
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def set_cookie(self, name: str, value: str):
        self.session.cookies.set(name, value)

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        logger.info(f"[API] {method.upper()} {url}")

        resp = self.session.request(method, url, **kwargs)
        logger.info(f"[API] Status: {resp.status_code}")

        allure.attach(
            body=f"{method.upper()} {url}\nStatus: {resp.status_code}\nResponse: {resp.text[:2000]}",
            name=f"API {method.upper()} {path}",
            attachment_type=allure.attachment_type.TEXT,
        )

        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}

    def get(self, path: str, **kwargs):
        return self._request("get", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._request("post", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self._request("put", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._request("delete", path, **kwargs)
