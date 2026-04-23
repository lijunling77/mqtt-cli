# -*- coding: utf-8 -*-
"""
HTTP 请求工具模块
"""
import json
import logging
from urllib.parse import urlparse

import requests
from fake_useragent import UserAgent
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


def requests_http(req_url, headers=None, request_type=None, request_body=None,
                  # 兼容旧参数名
                  req_Url=None, requestsType=None, requestsBody=None):
    """
    发送 HTTP 请求，返回 JSON 响应。

    :param req_url: 请求 URL
    :param headers: 请求头
    :param request_type: 请求类型 (GET/POST)
    :param request_body: 请求体 (JSON 字符串)
    :return: JSON 响应 dict 或 None
    """
    # 兼容旧参数名
    url = req_url or req_Url
    method = request_type or requestsType or "GET"
    body = request_body or requestsBody

    if not url or not isinstance(url, str):
        logger.error("请求 URL 无效")
        return None

    if headers is None:
        agent = UserAgent()
        parsed = urlparse(url)
        headers = {
            'User-Agent': agent.random,
            'Referer': f'{parsed.scheme}://{parsed.netloc}',
            'Host': parsed.netloc,
        }

    try:
        if method.upper() == "POST":
            response = requests.post(url=url, data=body, headers=headers,
                                     timeout=60, verify=False)
        else:
            response = requests.get(url=url, headers=headers,
                                    timeout=60, verify=False)
        response.encoding = response.apparent_encoding
        return response.json()
    except requests.Timeout:
        logger.error(f"请求超时: {url}")
        return None
    except Exception as e:
        logger.error(f"请求失败: {url} -> {e}")
        return None
