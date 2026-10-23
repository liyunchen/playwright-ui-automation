import logging

from common.api_client import ApiClient

logger = logging.getLogger("qa_test")


def api_login(client: ApiClient, username: str, password: str) -> ApiClient:
    """通过 API 登录 QA 平台并设置 token。

    平台实际登录接口为 POST /api/v1/auth/login，
    响应体形如 {"code": 0, "data": {"access_token": "...", "token_type": "bearer"}}
    """
    logger.info(f"[API] 登录 QA 平台: {username}")
    resp = client.post("/auth/login", json={"username": username, "password": password})

    token = None
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, dict):
            token = data.get("access_token") or data.get("token")
        if not token:
            token = resp.get("access_token") or resp.get("token")

    if token:
        client.set_token(token)
        logger.info("[API] 登录成功，token 已设置")
    else:
        logger.warning(f"[API] 响应中未找到 token: {resp}")

    return client