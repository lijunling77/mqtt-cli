# -*- coding: utf-8 -*-
import json
import os
import random
import sys
import time
import datetime
import logging
from requests_charge import requests_http

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from mqtt_connect import Subscription
from mqtt_msg_dc import MqttMsgDC

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(funcName)s -> %(message)s')

def generate_trade_id():
    now = datetime.datetime.now()
    return now.strftime("%y%m%d%H%M")

def generate_time(offset=0):
    now = datetime.datetime.now()
    t = now + datetime.timedelta(seconds=offset)
    return t.strftime("%Y%m%d%H%M%S")

class MqttPub:
    def __init__(self, mqtt_instantiation, mqtt_client, public_pile, pile_addr):
        self.mqtt_instantiation = mqtt_instantiation
        self.mqtt_client = mqtt_client
        self.public_pile = public_pile
        self.pile_addr = pile_addr

    def publish_update_msg(self, message):
        public_pile_update_topic = "/" + self.public_pile + "/" + self.pile_addr + "/update"
        self.mqtt_instantiation.on_publish(self.mqtt_client, public_pile_update_topic, message, 0)

    def dc_start_charging(self, cif=1, vin="", is_scan_start=False, uid=None,soc=None, beginSoC=None, endSoC=None, batType=None, get_gunQrCode_url1="",get_gunQrCode_url2= ""):

        sleep_time = int(random.uniform(1, 2))
        sleep_time_starting = int(random.uniform(1, 2))
        cycles_number = int(random.uniform(2, 2))
        m = MqttMsgDC()
        now = datetime.datetime.now()
        trade_id = int(now.strftime("%y%m%d%H%M"))
        energy_random = True  # 是否随机电量
        if energy_random:
            energy1 = round(float(random.uniform(1, 10)), 3)
            energy2 = round(float(random.uniform(1, 10)), 3)
            energy3 = round(float(random.uniform(1, 10)), 3)
            energy4 = round(float(random.uniform(1, 10)), 3)
        else:
            energy1 = 0.123
            energy2 = 0.456
            energy3 = 3.789
            energy4 = 2.987
        energy = energy1 + energy2 + energy3 + energy4

        t1 = generate_time()
        t2 = generate_time(10)
        t3 = generate_time(200)
        # 900s=15分钟
        t4 = generate_time(300)
        t5 = generate_time(int(random.uniform(1300, 2300)))  # 占位时间
        # t5 = generate_time(901)  # 占位时间


        # 更新为空闲
        for i in range(cycles_number):
            self.publish_update_msg(
                m.publish_yx(cif=cif, status=0, time=generate_time(), error=0, errcode="", alarm=0,
                             alarm1=0,
                             alarm2=0,
                             alarm3=0,
                             alarm4=0, alarm5=0, alarm6=0, alarm7=0, alarm8=0, yx1=0, yx2=0, yx3=0, yx4=0, yx5=0, yx6=0,
                             yx7=0, yx8=0))
            time.sleep(sleep_time)
        if is_scan_start:

            # 扫码插枪
            self.publish_update_msg(m.publish_yx(cif=cif, status=5, time=generate_time(), error=0, errcode="", alarm=0,
                         alarm1=0,
                         alarm2=0,
                         alarm3=0,
                         alarm4=0, yx1=1, yx2=0, yx3=0, yx4=0, yx5=0, yx6=0, yx7=0))
            time.sleep(sleep_time)

            # 雷神请求二维码解析
            get_gunQrCode_url1 = get_gunQrCode_url1
            equip_search_body = {"pileNo": pile_addr}
            chargePlatform_header_dict = {"Content-Type": "application/json; charset=UTF-8", "logan": "true",
                                          "xp-thor-skip-auth": "true",
                                          "xp-thor-user-id": uid}
            response_text = requests_http(
                req_Url=get_gunQrCode_url1,
                headers=chargePlatform_header_dict,
                requestsType="POST",
                requestsBody=json.dumps(equip_search_body))
            try:
                gunQrCode = response_text["data"]["records"][0]["gunList"][0]["gunQrCode"]
            except Exception as e:
                gunQrCode = ""
                logging.error(f'gunQrCode获取失败： {response_text}-> 原因：{e}')

            # App请求创建订单
            get_gunQrCode_url2 = get_gunQrCode_url2
            chargeOrder_body = {
                "qrCode": gunQrCode,
                "settleType": "01",
                "test": True
            }
            app_header_dict = {"Content-Type": "application/json; charset=UTF-8", "xp-client-type": "1",
                               "xp-uid": uid}
            response_text = requests_http(
                req_Url=get_gunQrCode_url2,
                headers=app_header_dict,
                requestsType="POST",
                requestsBody=json.dumps(chargeOrder_body))
            try:
                orderID = response_text["data"]["orderNo"]
                if orderID == "null" or orderID is None:
                    raise Exception(f'链接内容响应错误：{orderID}')
            except Exception as e:
                logging.error(f'gunQrCode获取失败： {response_text}-> 原因：{e}')
                orderID = ""
            print(orderID)

            # 桩启动中

            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID=orderID, vin=vin, type=1, state=1,
                                      bmsPVer='V0.0',
                                      batVendor='', batNo=-1, batDate='', batChaTimes=-1, batProperty=-1,
                                      bmsSoftVer=''))

            self.publish_update_msg(
                m.publish_yx(cif=1, status=5, time=generate_time(), error=0, errcode='', alarm=1,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))


            time.sleep(5)

            self.publish_update_msg(
                m.publish_yx(cif=1, status=5, time=generate_time(), error=0, errcode='', alarm=1,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))


            time.sleep(10)
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID=orderID, vin=vin, type=1, state=2,
                                      bmsPVer='V0.0',
                                      batVendor='', batNo=-1, batDate='', batChaTimes=-1, batProperty=-1,
                                      bmsSoftVer=''))
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID=orderID, vin=vin, type=1, state=3,
                                      bmsPVer='V0.0',
                                      batVendor='', batNo=-1, batDate='', batChaTimes=-1, batProperty=-1,
                                      bmsSoftVer=''))
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID=orderID, vin=vin, type=1, state=4,
                                      bmsPVer='V0.0',
                                      batVendor='', batNo=-1, batDate='', batChaTimes=-1, batProperty=-1,
                                      bmsSoftVer=''))

            # time.sleep(900)

            self.publish_update_msg(
                m.publish_yx(cif=1, status=0, time=generate_time(), error=0, errcode='', alarm=1,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))

            self.publish_update_msg(
                m.publish_yx(cif=1, status=0, time=generate_time(), error=0, errcode='', alarm=1,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))
            time.sleep(1)

            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID=orderID, vin=vin, type=1, state=4,  reason=0, errcode= '',bmsPVer='V0.0',
                                      batVendor='', batNo=-1, batDate='', batChaTimes=-1, batProperty=-1,
                                      bmsSoftVer=''))
            time.sleep(1)

            self.publish_update_msg(
                m.publish_yx(cif=1, status=0, time=generate_time(), error=0, errcode='', alarm=1,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID=orderID, vin=vin, type=1, state=5, reason=0,
                                      batType=batType, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                                      maxAllowCur=376.1,
                                      ratedVol=345.6,
                                      batVol=336.0, ratedAH=231.9, ratedKWh=74.0, batSOC=11.6, maxOutVol=500.0,
                                      minOutVol=200.0,
                                      maxOutCur=200.0,
                                      minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1', batVendor='', batNo=-1,
                                      batDate='',
                                      batChaTimes=-1, batProperty=-1, bmsSoftVer=''))
            # time.sleep(2000)

        else:
            orderID = ""  # 即插即充订单号可以为空

            # 插枪，桩开始即插即充
            self.publish_update_msg(m.publish_carchk(cif=1, vin="TEST2K0Y5JI4P6BC7", psuID='', psuAuthRes=99, vsrc='0', mfrs='', pwd=''))
            time.sleep(sleep_time_starting)
            self.publish_update_msg(
                m.publish_yx(cif=1, status=1, time=generate_time(), error=0, errcode='', alarm=0,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=0, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))

            # 桩启动中
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID='', vin=vin, type=0, state=0, bmsPVer='V0.0',
                                      batVendor='', batNo=-1, batDate='', batChaTimes=-1, batProperty=-1,
                                      bmsSoftVer=''))
            time.sleep(sleep_time_starting)
            self.publish_update_msg(
                m.publish_yx(cif=1, status=1, time=generate_time(), error=0, errcode='', alarm=1,
                             alarm1=0,
                             alarm2=0, alarm3=0,
                             alarm4=0, yx1=1, yx2=0, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))
            time.sleep(sleep_time_starting)
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID='', vin=vin, type=0, state=1, reason=0,
                                      batType=batType, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                                      maxAllowCur=376.1,
                                      ratedVol=345.6,
                                      batVol=336.0, ratedAH=231.9, ratedKWh=74, batSOC=11.6, maxOutVol=500.0,
                                      minOutVol=200.0,
                                      maxOutCur=200.0,
                                      minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1', batVendor='', batNo=-1,
                                      batDate='',
                                      batChaTimes=-1, batProperty=-1, bmsSoftVer=''))
            time.sleep(1)
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID='', vin=vin, type=0, state=2, reason=0,
                                      batType=batType, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                                      maxAllowCur=376.1,
                                      ratedVol=345.6,
                                      batVol=336.0, ratedAH=231.9, ratedKWh=74, batSOC=11.6, maxOutVol=500.0,
                                      minOutVol=200.0,
                                      maxOutCur=200.0,
                                      minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1', batVendor='', batNo=-1,
                                      batDate='',
                                      batChaTimes=-1, batProperty=-1, bmsSoftVer=''))
            time.sleep(1)
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID='', vin=vin, type=0, state=3, reason=0,
                                      batType=batType, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                                      maxAllowCur=376.1,
                                      ratedVol=345.6,
                                      batVol=336.0, ratedAH=231.9, ratedKWh=74, batSOC=11.6, maxOutVol=500.0,
                                      minOutVol=200.0,
                                      maxOutCur=200.0,
                                      minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1', batVendor='', batNo=-1,
                                      batDate='',
                                      batChaTimes=-1, batProperty=-1, bmsSoftVer=''))
            time.sleep(1)
            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID='', vin=vin, type=0, state=4, reason=0,
                                      batType=batType, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                                      maxAllowCur=376.1,
                                      ratedVol=345.6,
                                      batVol=336.0, ratedAH=231.9, ratedKWh=74, batSOC=11.6, maxOutVol=500.0,
                                      minOutVol=200.0,
                                      maxOutCur=200.0,
                                      minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1', batVendor='', batNo=-1,
                                      batDate='',
                                      batChaTimes=-1, batProperty=-1, bmsSoftVer=''))
            time.sleep(1)

            self.publish_update_msg(
                m.publish_dc_starting(cif=1, tradeID=trade_id, orderID='', vin=vin, type=0, state=5, reason=0,
                                      batType=batType, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                                      maxAllowCur=376.1,
                                      ratedVol=345.6,
                                      batVol=336.0, ratedAH=250.9, ratedKWh=74, batSOC=11.6, maxOutVol=500.0,
                                      minOutVol=200.0,
                                      maxOutCur=200.0,
                                      minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='2.0.1', batVendor='', batNo=-1,
                                      batDate='',
                                      batChaTimes=-1, batProperty=-1, bmsSoftVer=''))
            time.sleep(1)

        # 桩启动成功，开始上报电量信息
        self.publish_update_msg(
            m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=392.3, r_cur=-511.3, mode=2, soc=soc, remainTime=16,
                            cellMaxVol=4.09,
                            minTemp=33, maxTemp=135, m_vol=220.0, m_cur=-500.0))

        time.sleep(sleep_time)
        # return
        # time.sleep(20)
        # self.publish_update_msg(
        #     m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=392.3, r_cur=-511.3, mode=2, soc=soc, remainTime=16,
        #                     cellMaxVol=4.09,
        #                     minTemp=33, maxTemp=135, m_vol=220.0, m_cur=-500.0))
        # time.sleep(20)
        # self.publish_update_msg(
        #     m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=502.3, r_cur=-371.3, mode=2, soc=soc, remainTime=16,
        #                     cellMaxVol=4.09,
        #                     minTemp=33, maxTemp=35, m_vol=220.0, m_cur=-300.0))
        # time.sleep(20)
        # self.publish_update_msg(
        #     m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=392.3, r_cur=-111.3, mode=2, soc=soc, remainTime=16,
        #                     cellMaxVol=4.09,
        #                     minTemp=33, maxTemp=35, m_vol=220.0, m_cur=-100.0))
        #
        # time.sleep(20)
        # self.publish_update_msg(
        #     m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=392.3, r_cur=-1271.3, mode=2, soc=soc, remainTime=16,
        #                     cellMaxVol=4.09,
        #                     minTemp=33, maxTemp=35, m_vol=888.89, m_cur=-967.0))
        # time.sleep(20)
        # self.publish_update_msg(
        #     m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=392.3, r_cur=-310, mode=2, soc=soc, remainTime=16,
        #                     cellMaxVol=4.09,
        #                     minTemp=33, maxTemp=35, m_vol=20.0, m_cur=-300.0))
        # time.sleep(20)
        #return

        self.publish_update_msg(m.publish_yx(cif=cif, status=1, time=generate_time(), error=0, errcode='', alarm=1,
                                             alarm1=0,
                                             alarm2=0,
                                             alarm3=0,
                                             alarm4=0, yx1=1, yx2=1, yx3=1, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))
        self.publish_update_msg(m.publish_ycMeas(tradeID=trade_id, t2=generate_time(), time=53,
                                                 energy=energy,
                                                 energy1=energy1,
                                                 energy2=energy2,
                                                 energy3=energy3,
                                                 energy4=energy4,
                                                 secEnergy=0.000, secEnergy1=0.000,
                                                 secEnergy2=0.000,
                                                 secEnergy3=0.000, secEnergy4=0.000, meterEnergy=327850.656,
                                                 acMeterEnergy=6069.844))
        time.sleep(sleep_time)
        # 暂停在充电中 5分钟
        # time.sleep(300)
        # 结束在充电中
        # return


        # 结束充电
        self.publish_update_msg(m.publish_chargend(cif=cif, tradeID=trade_id, orderID=orderID, vin=vin, t1=t1,
                                                   t2=t2,
                                                   t3=t3, t4=t4,
                                                   energy=energy,
                                                   energy1=energy1,
                                                   energy2=energy2,
                                                   energy3=energy3,
                                                   energy4=energy4,
                                                   secEnergy=0.000, secEnergy1=0.000, secEnergy2=0.000,
                                                   secEnergy3=0.000,
                                                   secEnergy4=0.000,
                                                   time=3, time1=1, time2=0, time3=0, beginSoC=beginSoC, endSoC=endSoC, csr=114, errCode="E45"))
        for i in range(cycles_number):
            self.publish_update_msg(m.publish_yx(cif=cif, status=2, time=generate_time(), error=0, errcode='', alarm=1,
                                                 alarm1=0,
                                                 alarm2=0,
                                                 alarm3=0,
                                                 alarm4=0, yx1=1, yx2=0, yx3=0, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))
        time.sleep(sleep_time)
        # 暂停在充电完成 5分钟
        # time.sleep(300)
        # 结束在充电完成
        # return

        # 上报交易信息
        self.publish_update_msg(
            m.publish_trade(cif=cif, tradeID=trade_id, orderID=orderID, vin=vin, t1=t1, t2=t2,
                            t3=t3, t4=t4, t5=t5, t6='',
                            energy=energy,
                            energy1=energy1,
                            energy2=energy2,
                            energy3=energy3,
                            energy4=energy4,
                            secEnergy=0.000, secEnergy1=0.000, secEnergy2=0.000,
                            secEnergy3=0.000,
                            secEnergy4=-0.000, time=3, time1=1, time2=0, time3=0, beginSoC=beginSoC,
                            endSoC=endSoC, csr=114))
        time.sleep(sleep_time)

        # 更新到空闲
        self.publish_update_msg(
            m.publish_yx(cif=cif, status=0, time=generate_time(), error=0, errcode='', alarm=1,
                         alarm1=0,
                         alarm2=0,
                         alarm3=0,
                         alarm4=0, yx1=0, yx2=0, yx3=0, yx4=0, yx5=0, yx6=0, yx7=0, rssi=31))


# 定义配置信息
CONFIGS = {
        "pre": {
            "pile_addr": "XPAC2017YS03240002",  # 张三专用（共建6）XPDC6250ZC22040002,XPAC2007YS03240003,20230136351001   20230136530001  20230136526003
            "vin": "TEST2K0Y5JI4P6BC7",  # 即插即冲不为空 非小鹏车：L1NNSGHB3NB000199 ，小鹏车：TESTS5QV218D0HGRZ、TESTK864ZLGCXPAE3
            "public_pile": "XPeng_10002_Charge",#L1NNSGHB3NB000161
            "uid": "8102985",  #8133247
            "mqtt_username": "charge-mqtt",
            "mqtt_password": "vTZLRlmlDJiR",
            "get_gunQrCode_url1": "https://thor.deploy-test.xiaopeng.com/api/xp-thor-asset/asset/equip/search",
            "get_gunQrCode_url2": "https://xmart.deploy-test.xiaopeng.com/biz/v5/chargeOrder/chargeOrderV2"
        },
        "test": {
            "pile_addr": "559847003",  # 张三专用 合作超充 旧共建
            "vin": "TESTNUYCXPKWVTIZF",
            "public_pile": "XPeng_TEST_Charge",
            "uid": "1160057",
            "mqtt_username": "charge-private-mqtt",
            "mqtt_password": "0LZVRlmlD88Y",
            "get_gunQrCode_url1": "http://thor.test.xiaopeng.local/api/xp-thor-asset/asset/equip/search",
            "get_gunQrCode_url2": "https://10.0.13.28:8553/biz/v5/chargeOrder/chargeOrderV2"

        }
    }
config1 = {
    "soc": 90,  # BMSSoC
    "beginSoC": 20,
    "endSoC": 90,
    "batType": 3
    # 3为磷酸铁锂 ,6为三元锂
    # 电池类型
}
if __name__ == '__main__':
    # 选择环境
    selected_config = "pre"

    # 提取配置信息
    config = CONFIGS[selected_config]
    pile_addr = config["pile_addr"]
    vin = config["vin"]
    public_pile = config["public_pile"]
    uid = config["uid"]
    get_gunQrCode_url1 = config["get_gunQrCode_url1"]
    get_gunQrCode_url2 = config["get_gunQrCode_url2"]
    mqtt_username = config["mqtt_username"]
    mqtt_password = config["mqtt_password"]
    soc = config1["soc"]
    beginSoC = config1["beginSoC"]
    endSoC = config1["endSoC"]
    batType = config1["batType"]

    # 启动相关操作
    mqtt_server_ip = "47.96.240.241"
    mqtt_server_port = 12883
    mqtt_instantiation = Subscription(mqtt_server_ip, mqtt_server_port, mqtt_username, mqtt_password)
    mqtt_client = mqtt_instantiation.mqtt_connect()
    mqtt_pub = MqttPub(mqtt_instantiation, mqtt_client, public_pile, pile_addr)

    # 定义启动参数
    start_charging_params_scan = {
        "cif": 1,
        "vin": vin,
        "is_scan_start": True,
        "uid": uid,
        "get_gunQrCode_url1": get_gunQrCode_url1,
        "get_gunQrCode_url2": get_gunQrCode_url2,
        "soc": soc,
        "beginSoC": beginSoC,
        "endSoC": endSoC,
        "batType": batType
    }
    start_charging_params = {
        "cif": 1,
        "vin": vin,
        "soc": soc,
        "beginSoC": beginSoC,
        "endSoC": endSoC,
        "batType": batType
    }

    # 扫码启动
    # mqtt_pub.dc_start_charging(**start_charging_params_scan)
    # 即插即充
    # mqtt_pub.dc_start_charging(**start_charging_params)

    # 循环执行
    # 指定循环次数
    loop_count = 1

    for _ in range(loop_count):
        try:
            mqtt_pub.dc_start_charging(**start_charging_params_scan)
            time.sleep(10)
        except Exception as e:
            print(f"执行过程中出现错误: {e}")