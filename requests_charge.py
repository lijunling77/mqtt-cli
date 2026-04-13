import json
import logging
from urllib.parse import urlparse
import requests
from fake_useragent import UserAgent
# 禁用requests出现的取消ssl验证的警告，直接引用如下
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(funcName)s -> %(message)s')

# uid = "1160057"  # 测试
#
#
# # uid = "8102985"  #预发


def requests_http(
        req_Url: str or list, headers: dict = None, proxies: dict = None,
        requestsType: str = None, requestsBody: str = None) -> bool or str or json:
    """
    1、下载图片

    :param requestsBody: Body
    :param requestsType: 类型
    :param req_Url: 下载的图片链接或者列表
    :param headers: 自定义头部信息
    :param proxies: 自定义代理
    :return:
    """
    agent = UserAgent()
    if isinstance(req_Url, str):

        req_UrlParse = urlparse(req_Url)

        if headers is None:
            headers = {
                'User-Agent': agent.random,
                'Referer': f'{req_UrlParse.scheme}://{req_UrlParse.netloc}',
                'Host': req_UrlParse.netloc,
            }
        # 下载
        try:
            if requestsType == "POST":
                response = requests.post(url=req_Url, data=requestsBody, headers=headers, timeout=60,
                                         proxies=proxies, verify=False)
            else:
                response = requests.get(url=req_Url, headers=headers, timeout=60, proxies=proxies, verify=False)
            response.encoding = response.apparent_encoding

            # 判断code值
            response_json = json.loads(response.text)
            print(response_json)
            return response_json
            # if response_text["code"] != 1:
            #     raise Exception(f'链接Code响应错误：{req_Url[i]}')
            # if response_text["data"] == {}:
            #     raise Exception(f'链接内容响应错误：{req_Url[i]}')
        except TimeoutError:
            logging.error(f'请求超时：{req_Url}')
        except Exception as e:
            logging.error(f'请求失败：{req_Url} ->{requestsBody}-> 原因：{e}')
    else:
        logging.error('请求错误！')


def header_chargePlatform() -> dict:
    header_dict = {"Content-Type": "application/json; charset=UTF-8", "logan": "true", "xp-thor-skip-auth": "true",
                   "xp-thor-user-id": "8102985"}
    return header_dict


def header_chargeAPP() -> dict:
    header_dict = {"Content-Type": "application/json; charset=UTF-8", "xp-client-type": "1", "xp-uid": "8102985"}
    return header_dict


# def body_handle_chargeAPP(requestsBody: dict = None) -> dict:
#     requestsBody["test"] = "true"
#     return requestsBody


if __name__ == '__main__':
    addr = "XPAC6250ZH23100005"
    # addr = "555722001"

    # 雷神请求二维码解析 https://thor.deploy-test.xiaopeng.com/api/xp-thor-asset/asset/equip/search
    get_gunQrCode_url = "https://thor.deploy-test.xiaopeng.com/api/xp-thor-asset/asset/equip/search"
    # get_gunQrCode_url = "http://thor.test.xiaopeng.local/api/xp-thor-asset/asset/equip/search"

    equip_search_body = {"pileNo": addr}
    chargePlatform_header_dict = {"Content-Type": "application/json; charset=UTF-8", "logan": "true", "xp-thor-skip-auth": "true",
                   "xp-thor-user-id": "8102985"}
    response_text = requests_http(
        req_Url=get_gunQrCode_url,
        headers=chargePlatform_header_dict,
        requestsType="POST",
        requestsBody=json.dumps(equip_search_body))
    try:
        gunQrCode = response_text["data"]["records"][0]["gunList"][0]["gunQrCode"]
    except Exception as e:
        gunQrCode = ""
        logging.error(f'gunQrCode获取失败： {response_text}-> 原因：{e}')

    # App请求创建订单 https://xmart.deploy-test.xiaopeng.com/biz/v5/chargeOrder/chargeOrderV2
    get_gunQrCode_url = "https://xmart.deploy-test.xiaopeng.com/biz/v5/chargeOrder/chargeOrderV2"
    # get_gunQrCode_url = "http://xmart.test.xiaopeng.local/biz/v5/chargeOrder/chargeOrderV2"

    chargeOrder_body = {
        "qrCode": "hlht://47756771.MA59CU773/",
        "settleType": "01",
        "test": True
    }
    app_header_dict = {"Content-Type": "application/json; charset=UTF-8", "xp-client-type": "1", "xp-uid": "8102985"}
    response_text = requests_http(
        req_Url=get_gunQrCode_url,
        headers=app_header_dict,
        requestsType="POST",
        requestsBody=json.dumps(chargeOrder_body))
    try:
        orderNo = response_text["data"]["orderNo"]
        if orderNo == "null" or orderNo is None:
            raise Exception(f'链接内容响应错误：{orderNo}')
    except Exception as e:
        logging.error(f'gunQrCode获取失败： {response_text}-> 原因：{e}')
        orderNo = ""
    print("orderNo:", orderNo)
