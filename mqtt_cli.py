# -*- coding: utf-8 -*-
"""
MQTT 充电桩模拟 CLI 工具
"""
import argparse
import json
import os
import sys
import time
import random
import datetime
import logging

try:
    import yaml
except ImportError:
    yaml = None

from mqtt_connect import Subscription
from mqtt_msg_dc import MqttMsgDC
from requests_charge import requests_http

logging.basicConfig(level=logging.INFO, format='%(asctime)s -> %(message)s')

# ─── 多环境配置 ───
ENV_CONFIG = {
    "pre": {
        "mqtt_ip": "47.96.240.241",
        "mqtt_port": 12883,
        "mqtt_user": "charge-mqtt",
        "mqtt_pwd": "vTZLRlmlDJiR",
        "public_pile": "XPeng_10002_Charge",
        "url_equip": "https://thor.deploy-test.xiaopeng.com/api/xp-thor-asset/asset/equip/search",
        "url_order": "https://xmart.deploy-test.xiaopeng.com/biz/v5/chargeOrder/chargeOrderV2",
        "pile": "XPAC2017YS03240002",
        "vin": "TEST2K0Y5JI4P6BC7",
        "uid": "8102985",
    },
    "test": {
        "mqtt_ip": "47.96.240.241",
        "mqtt_port": 12883,
        "mqtt_user": "charge-private-mqtt",
        "mqtt_pwd": "0LZVRlmlD88Y",
        "public_pile": "XPeng_TEST_Charge",
        "url_equip": "http://thor.test.xiaopeng.local/api/xp-thor-asset/asset/equip/search",
        "url_order": "https://10.0.13.28:8553/biz/v5/chargeOrder/chargeOrderV2",
        "pile": "559847003",
        "vin": "TESTNUYCXPKWVTIZF",
        "uid": "1160057",
    },
}


# ─── 配置管理 ───

def load_config(config_path="config.yaml"):
    """加载 YAML 配置文件，不存在则返回空 dict"""
    if os.path.exists(config_path):
        if yaml is None:
            logging.warning("未安装 pyyaml，无法加载配置文件，使用内置默认值")
            return {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.warning(f"加载配置文件失败: {e}，使用内置默认值")
    return {}

def merge_config(env_name, file_config):
    """合并配置：文件配置覆盖内置 ENV_CONFIG"""
    # 内置默认值
    base = ENV_CONFIG.get(env_name, ENV_CONFIG["pre"]).copy()

    # 文件中的环境配置覆盖
    file_envs = file_config.get("environments", {})
    if env_name in file_envs:
        base.update(file_envs[env_name])

    # 环境变量覆盖敏感信息
    env_var_key = f"MQTT_PWD_{env_name.upper()}"
    env_pwd = os.environ.get(env_var_key)
    if env_pwd:
        base["mqtt_pwd"] = env_pwd

    return base

def get_defaults(file_config):
    """获取默认参数，文件配置覆盖内置默认值"""
    defaults = {
        "env": "pre", "cif": 1, "speed": 2.0,
        "soc": 90, "bsoc": 20, "esoc": 90, "bat": 3,
        "rated_ah": 231.9, "rated_kwh": 74,
    }
    file_defaults = file_config.get("defaults", {})
    defaults.update(file_defaults)
    return defaults


class DualLogger:
    """同时输出到终端和日志文件"""
    def __init__(self, log_dir="./logs/"):
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        self.f = open(self.log_file, 'a', encoding='utf-8')

    def write(self, text):
        """写入日志文件（去除 ANSI 颜色码，密码脱敏）"""
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', text)
        # 密码脱敏
        for key in ["mqtt_pwd", "password", "pwd"]:
            if key in clean:
                clean = re.sub(rf'"{key}":\s*"[^"]*"', f'"{key}": "***"', clean)
        self.f.write(clean + '\n')
        self.f.flush()

    def close(self):
        self.f.close()


def ts(offset=0):
    return (datetime.datetime.now() + datetime.timedelta(seconds=offset)).strftime("%Y%m%d%H%M%S")

def make_tid():
    return int(datetime.datetime.now().strftime("%y%m%d%H%M"))

def rand_e():
    e = [round(random.uniform(1, 10), 3) for _ in range(4)]
    return e, round(sum(e), 3)

def step(msg):
    print(f"\n  \033[93m▶ {msg}\033[0m")

def ok(msg):
    print(f"    \033[92m✓\033[0m {msg}")

def pub_log(label, payload):
    short = payload[:120] + ("..." if len(payload) > 120 else "")
    print(f"    \033[96m→ [{label}]\033[0m {short}")


# ─── 参数校验 ───

def validate_vin(vin):
    """校验 VIN 码"""
    if len(vin) != 17:
        print(f"    \033[91m✗ VIN 码必须为 17 位，当前输入 {len(vin)} 位\033[0m")
        return False
    return True

def validate_soc(soc, bsoc, esoc):
    """校验 SOC 参数"""
    for name, val in [("SOC", soc), ("开始SOC", bsoc), ("结束SOC", esoc)]:
        if not (0 <= val <= 100):
            print(f"    \033[91m✗ {name} 必须在 0-100 范围内，当前值 {val}\033[0m")
            return False
    if bsoc >= esoc:
        print(f"    \033[91m✗ 开始SOC({bsoc}) 必须小于结束SOC({esoc})\033[0m")
        return False
    return True

def validate_bat(bat):
    """校验电池类型"""
    if bat not in (3, 6):
        print(f"    \033[91m✗ 电池类型必须为 3(磷酸铁锂) 或 6(三元锂)，当前值 {bat}\033[0m")
        return False
    return True


# ─── 预设数据常量 ───
SUMMARY_BMS_SEQUENCE = [
    {"r_vol": 392.3, "r_cur": -71.3,  "m_vol": 220.0,  "m_cur": -300.0},
    {"r_vol": 392.3, "r_cur": -271.3, "m_vol": 220.0,  "m_cur": -300.0},
    {"r_vol": 392.3, "r_cur": -271.3, "m_vol": 888.89, "m_cur": -967.0},
    {"r_vol": 392.3, "r_cur": -171.3, "m_vol": 20.0,   "m_cur": -300.0},
]

SATISFACTION_PRESETS = {
    "normal":   {"r_vol": 392.3, "r_cur": -512.3, "m_vol": 223.0, "m_cur": -503.0},
    "mismatch": {"r_vol": 500.1, "r_cur": -309.8, "m_vol": 223.0, "m_cur": -294.1},
    "shunt":    {"r_vol": 400.3, "r_cur": -212.3, "m_vol": 223.0, "m_cur": -103.0},
}

IDENTITY_THEFT_PRESETS = {
    "normal":    {"bat": 3, "rated_ah": 231.9, "rated_kwh": 74},
    "bat-type":  {"bat": 6, "rated_ah": 231.9, "rated_kwh": 74},
    "ah-bias":   {"bat": 3, "rated_ah": 211.9, "rated_kwh": 74},
    "kwh-bias":  {"bat": 3, "rated_ah": 231.9, "rated_kwh": 83.0},
}

CD_RESULT_MAP = {
    1: {"errcode": 0, "errmsg": "成功"},
    2: {"errcode": 1, "errmsg": "平台终止"},
    3: {"errcode": 2, "errmsg": "BMS禁止充检"},
    4: {"errcode": 3, "errmsg": "BEX1超时"},
    5: {"errcode": 4, "errmsg": "暂停充电超时"},
    6: {"errcode": 5, "errmsg": "脉冲输出超时"},
    7: {"errcode": 6, "errmsg": "脉冲电流停止超时"},
    8: {"errcode": 7, "errmsg": "充检时结束充电"},
    9: {"errcode": 99, "errmsg": "其他错误"},
}


class Charger:
    def __init__(self, pile, speed=2.0, env="pre"):
        cfg = ENV_CONFIG[env]
        self.pile = pile
        self.speed = speed
        self.env = env
        self.cfg = cfg
        self.m = MqttMsgDC()
        self.sub = Subscription(cfg["mqtt_ip"], cfg["mqtt_port"], cfg["mqtt_user"], cfg["mqtt_pwd"])
        self.client = self.sub.mqtt_connect()
        self.topic = f"/{cfg['public_pile']}/{pile}/update"

    def _send_bms_series(self, cif, tradeID, bsoc, esoc, count=4, interval=20, bms_params=None):
        """充电中阶段发送多条 SOC 递增的 ycBMS 报文"""
        for i in range(count):
            current_soc = bsoc + (esoc - bsoc) * i // max(count - 1, 1)
            remain = max(0, 16 - 16 * i // max(count - 1, 1))
            params = bms_params or {}
            self.pub(self.m.publish_ycBMS(
                cif=cif, tradeID=tradeID,
                r_vol=params.get("r_vol", 392.3), r_cur=params.get("r_cur", -511.3),
                mode=2, soc=current_soc, remainTime=remain, cellMaxVol=4.09,
                minTemp=33, maxTemp=35,
                m_vol=params.get("m_vol", 220.0), m_cur=params.get("m_cur", -500.0)
            ), f"ycBMS-{i+1}(SOC={current_soc})")
            self.w(interval)

    def send_boot_noti(self, pile_type=0, protocol_ver=119):
        """发送桩启动通知"""
        step("发送 bootNoti")
        self.pub(self.m.publish_bootNoti(p_ver=protocol_ver, type=pile_type, vendor="XPENG"), "bootNoti")
        self.w(1)

    def pub(self, msg, label=""):
        self.sub.on_publish(self.client, self.topic, msg, 0)
        pub_log(label, msg)

    def w(self, sec):
        time.sleep(max(sec / self.speed, 0.05))

    def subscribe_responses(self):
        """订阅平台响应 Topic"""
        get_topic = f"/{self.cfg['public_pile']}/{self.pile}/get"
        rrpc_topic = f"/{self.cfg['public_pile']}/{self.pile}/rrpc/request/+"
        self.sub.on_subscribe(self.client, get_topic)
        self.sub.on_subscribe(self.client, rrpc_topic)
        ok(f"已订阅响应 Topic: {get_topic}")

    def plug_charge(self, vin, cif, soc, bsoc, esoc, bat):
        """即插即充完整流程"""
        t = make_tid()
        es, energy = rand_e()
        t1, t2, t3, t4 = ts(), ts(10), ts(200), ts(300)
        t5 = ts(random.randint(1300, 2300))

        step("1/7 上报空闲")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts()), "yx-空闲")
            self.w(1)

        step("2/7 车辆验证")
        self.pub(self.m.publish_carchk(cif=cif, vin=vin, vsrc='0'), "carChk")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), yx1=1, rssi=31), "yx-工作")
        self.w(1)

        step("3/7 启动状态 state 0→5")
        for s in range(6):
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID='', vin=vin, type=0, state=s, reason=0,
                batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=231.9,
                ratedKWh=74, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
                maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
                batVendor='', batNo=-1, batDate='', batChaTimes=-1,
                batProperty=-1, bmsSoftVer=''
            ), f"starting-s{s}")
            self.w(1)

        step("4/7 上报 BMS/YX/YcMeas")
        self.pub(self.m.publish_ycBMS(cif=cif, tradeID=t, r_vol=392.3, r_cur=-511.3,
                 mode=2, soc=soc, remainTime=16, cellMaxVol=4.09,
                 minTemp=33, maxTemp=35, m_vol=220.0, m_cur=-500.0), "ycBMS")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), alarm=1,
                 yx1=1, yx2=1, yx3=1, rssi=31), "yx-充电中")
        self.pub(self.m.publish_ycMeas(tradeID=t, t2=ts(), time=53,
                 energy=energy, energy1=es[0], energy2=es[1],
                 energy3=es[2], energy4=es[3]), "ycMeas")
        self.w(2)

        step("5/7 结束充电")
        self.pub(self.m.publish_chargend(
            cif=cif, tradeID=t, orderID='', vin=vin, t1=t1, t2=t2, t3=t3, t4=t4,
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc,
            csr=114, errCode=""
        ), "chargEnd")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=2, time=ts(), alarm=1, yx1=1, rssi=31), "yx-完成")
        self.w(1)

        step("6/7 交易上传")
        self.pub(self.m.publish_trade(
            cif=cif, tradeID=t, orderID='', vin=vin, t1=t1, t2=t2, t3=t3, t4=t4, t5=t5, t6='',
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc, csr=114
        ), "trade")
        self.w(1)

        step("7/7 恢复空闲")
        self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), alarm=1, rssi=31), "yx-空闲")
        ok("即插即充完成 ✓")
        return (t, "")

    def scan_charge(self, vin, cif, uid, soc, bsoc, esoc, bat):
        """扫码充电完整流程"""
        t = make_tid()
        es, energy = rand_e()
        t1, t2, t3, t4 = ts(), ts(10), ts(200), ts(300)
        t5 = ts(random.randint(1300, 2300))

        step("1/8 上报空闲")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts()), "yx-空闲")
            self.w(1)

        step("2/8 扫码等待插枪")
        self.pub(self.m.publish_yx(cif=cif, status=5, time=ts(), yx1=1), "yx-等待插枪")
        self.w(1)

        step("3/8 获取二维码 & 创建订单")
        resp = requests_http(
            req_Url=self.cfg["url_equip"],
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "logan": "true", "xp-thor-skip-auth": "true",
                     "xp-thor-user-id": uid},
            requestsType="POST",
            requestsBody=json.dumps({"pileNo": self.pile}))
        qr = ""
        try:
            qr = resp["data"]["records"][0]["gunList"][0]["gunQrCode"]
            ok(f"gunQrCode: {qr}")
        except Exception as e:
            logging.error(f"获取 gunQrCode 失败: {e}")

        resp2 = requests_http(
            req_Url=self.cfg["url_order"],
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "xp-client-type": "1", "xp-uid": uid},
            requestsType="POST",
            requestsBody=json.dumps({"qrCode": qr, "settleType": "01", "test": True}))
        oid = ""
        try:
            oid = resp2["data"]["orderNo"] or ""
            ok(f"orderID: {oid}")
        except Exception as e:
            logging.error(f"创建订单失败: {e}")

        step("4/8 启动状态 state 1→5")
        for s in [1, 2, 3, 4]:
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID=oid, vin=vin, type=1, state=s,
                bmsPVer='V0.0', batVendor='', batNo=-1, batDate='',
                batChaTimes=-1, batProperty=-1, bmsSoftVer=''
            ), f"starting-s{s}")
            self.w(2)
        self.pub(self.m.publish_dc_starting(
            cif=cif, tradeID=t, orderID=oid, vin=vin, type=1, state=5, reason=0,
            batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
            maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=231.9,
            ratedKWh=74.0, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
            maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
            batVendor='', batNo=-1, batDate='', batChaTimes=-1,
            batProperty=-1, bmsSoftVer=''
        ), "starting-s5")
        self.w(1)

        step("5/8 上报 BMS/YX/YcMeas")
        self.pub(self.m.publish_ycBMS(cif=cif, tradeID=t, r_vol=392.3, r_cur=-511.3,
                 mode=2, soc=soc, remainTime=16, cellMaxVol=4.09,
                 minTemp=33, maxTemp=35, m_vol=220.0, m_cur=-500.0), "ycBMS")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), alarm=1,
                 yx1=1, yx2=1, yx3=1, rssi=31), "yx-充电中")
        self.pub(self.m.publish_ycMeas(tradeID=t, t2=ts(), time=53,
                 energy=energy, energy1=es[0], energy2=es[1],
                 energy3=es[2], energy4=es[3]), "ycMeas")
        self.w(2)

        step("6/8 结束充电")
        self.pub(self.m.publish_chargend(
            cif=cif, tradeID=t, orderID=oid, vin=vin, t1=t1, t2=t2, t3=t3, t4=t4,
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc,
            csr=114, errCode=""
        ), "chargEnd")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=2, time=ts(), alarm=1, yx1=1, rssi=31), "yx-完成")
        self.w(1)

        step("7/8 交易上传")
        self.pub(self.m.publish_trade(
            cif=cif, tradeID=t, orderID=oid, vin=vin, t1=t1, t2=t2, t3=t3, t4=t4, t5=t5, t6='',
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc, csr=114
        ), "trade")
        self.w(1)

        step("8/8 恢复空闲")
        self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), alarm=1, rssi=31), "yx-空闲")
        ok("扫码充电完成 ✓")
        return (t, oid)

    def scenario_summary(self, vin, cif, uid, soc, bsoc, esoc, bat, reason=114):
        """充电小结场景：扫码充电流程 + 多条不同功率 ycBMS"""
        t = make_tid()
        es, energy = rand_e()
        t1, t2, t3, t4 = ts(), ts(10), ts(200), ts(300)
        t5 = ts(random.randint(1300, 2300))

        step("1/9 上报空闲")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts()), "yx-空闲")
            self.w(1)

        step("2/9 扫码等待插枪")
        self.pub(self.m.publish_yx(cif=cif, status=5, time=ts(), yx1=1), "yx-等待插枪")
        self.w(1)

        step("3/9 获取二维码 & 创建订单")
        resp = requests_http(
            req_Url=self.cfg["url_equip"],
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "logan": "true", "xp-thor-skip-auth": "true",
                     "xp-thor-user-id": uid},
            requestsType="POST",
            requestsBody=json.dumps({"pileNo": self.pile}))
        qr = ""
        try:
            qr = resp["data"]["records"][0]["gunList"][0]["gunQrCode"]
            ok(f"gunQrCode: {qr}")
        except Exception as e:
            logging.error(f"获取 gunQrCode 失败: {e}")

        resp2 = requests_http(
            req_Url=self.cfg["url_order"],
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "xp-client-type": "1", "xp-uid": uid},
            requestsType="POST",
            requestsBody=json.dumps({"qrCode": qr, "settleType": "01", "test": True}))
        oid = ""
        try:
            oid = resp2["data"]["orderNo"] or ""
            ok(f"orderID: {oid}")
        except Exception as e:
            logging.error(f"创建订单失败: {e}")

        step("4/9 启动状态 state 1→5")
        for s in [1, 2, 3, 4]:
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID=oid, vin=vin, type=1, state=s,
                bmsPVer='V0.0', batVendor='', batNo=-1, batDate='',
                batChaTimes=-1, batProperty=-1, bmsSoftVer=''
            ), f"starting-s{s}")
            self.w(2)
        self.pub(self.m.publish_dc_starting(
            cif=cif, tradeID=t, orderID=oid, vin=vin, type=1, state=5, reason=0,
            batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
            maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=231.9,
            ratedKWh=74.0, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
            maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
            batVendor='', batNo=-1, batDate='', batChaTimes=-1,
            batProperty=-1, bmsSoftVer=''
        ), "starting-s5")
        self.w(1)

        step("5/9 上报多条 BMS 数据（充电小结）")
        for i, bms in enumerate(SUMMARY_BMS_SEQUENCE):
            self.pub(self.m.publish_ycBMS(
                cif=cif, tradeID=t, r_vol=bms["r_vol"], r_cur=bms["r_cur"],
                mode=2, soc=soc, remainTime=16, cellMaxVol=4.09,
                minTemp=33, maxTemp=35, m_vol=bms["m_vol"], m_cur=bms["m_cur"]
            ), f"ycBMS-{i+1}")
            self.w(20)

        step("6/9 上报 YX/YcMeas")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), alarm=1,
                 yx1=1, yx2=1, yx3=1, rssi=31), "yx-充电中")
        self.pub(self.m.publish_ycMeas(tradeID=t, t2=ts(), time=53,
                 energy=energy, energy1=es[0], energy2=es[1],
                 energy3=es[2], energy4=es[3]), "ycMeas")
        self.w(2)

        step("7/9 结束充电")
        self.pub(self.m.publish_chargend(
            cif=cif, tradeID=t, orderID=oid, vin=vin, t1=t1, t2=t2, t3=t3, t4=t4,
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc,
            csr=reason, errCode=""
        ), "chargEnd")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=2, time=ts(), alarm=1, yx1=1, rssi=31), "yx-完成")
        self.w(1)

        step("8/9 交易上传")
        self.pub(self.m.publish_trade(
            cif=cif, tradeID=t, orderID=oid, vin=vin, t1=t1, t2=t2, t3=t3, t4=t4, t5=t5, t6='',
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc, csr=reason
        ), "trade")
        self.w(1)

        step("9/9 恢复空闲")
        self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), alarm=1, rssi=31), "yx-空闲")
        ok("充电小结完成 ✓")
        return (t, oid)

    def scenario_battery_check_start(self, vin, cif, uid):
        """电池充检第一阶段：跑扫码充电到充电中状态(SOC<25)，返回(tradeID, orderID)"""
        t = make_tid()
        soc = 24  # SOC 必须小于 25
        bat = 3

        step("1/6 上报桩属性(cdEn=1)")
        self.pub(self.m.publish_pileProp(cdEn=1), "pileProp")
        self.w(1)

        step("2/6 上报空闲")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts()), "yx-空闲")
            self.w(1)

        step("3/6 扫码等待插枪")
        self.pub(self.m.publish_yx(cif=cif, status=5, time=ts(), yx1=1), "yx-等待插枪")
        self.w(1)

        step("4/6 获取二维码 & 创建订单")
        resp = requests_http(
            req_Url=self.cfg["url_equip"],
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "logan": "true", "xp-thor-skip-auth": "true",
                     "xp-thor-user-id": uid},
            requestsType="POST",
            requestsBody=json.dumps({"pileNo": self.pile}))
        qr = ""
        try:
            qr = resp["data"]["records"][0]["gunList"][0]["gunQrCode"]
            ok(f"gunQrCode: {qr}")
        except Exception as e:
            logging.error(f"获取 gunQrCode 失败: {e}")

        resp2 = requests_http(
            req_Url=self.cfg["url_order"],
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "xp-client-type": "1", "xp-uid": uid},
            requestsType="POST",
            requestsBody=json.dumps({"qrCode": qr, "settleType": "01", "test": True}))
        oid = ""
        try:
            oid = resp2["data"]["orderNo"] or ""
            ok(f"orderID: {oid}")
        except Exception as e:
            logging.error(f"创建订单失败: {e}")

        step("5/6 启动状态 state 1→5")
        for s in [1, 2, 3, 4]:
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID=oid, vin=vin, type=1, state=s,
                bmsPVer='V0.0', batVendor='', batNo=-1, batDate='',
                batChaTimes=-1, batProperty=-1, bmsSoftVer=''
            ), f"starting-s{s}")
            self.w(2)
        self.pub(self.m.publish_dc_starting(
            cif=cif, tradeID=t, orderID=oid, vin=vin, type=1, state=5, reason=0,
            batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
            maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=231.9,
            ratedKWh=74.0, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
            maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
            batVendor='', batNo=-1, batDate='', batChaTimes=-1,
            batProperty=-1, bmsSoftVer=''
        ), "starting-s5")
        self.w(1)

        step(f"6/6 上报 BMS (SOC={soc}, cdFlag=2) → 充电进行中")
        self.pub(self.m.publish_ycBMS(cif=cif, tradeID=t, r_vol=400.3, r_cur=-999,
                 mode=2, soc=soc, soc1=90, remainTime=16, cellMaxVol=4.09,
                 minTemp=33, maxTemp=35, m_vol=1499, m_cur=-999, cdFlag=2), "ycBMS-cdFlag")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), alarm=1,
                 yx1=1, yx2=1, yx3=1, rssi=31), "yx-充电中")

        ok(f"充电订单已跑到进行中 ✓(SOC={soc})")
        print(f"\n  \033[1;93m\U0001f4cb tradeID: {t}  |  orderID: {oid or '(空)'}\033[0m")
        return (t, oid)

    def scenario_battery_check_progress(self, trade_id, check_id, vin, cif=1, result_choice=1, interval=2):
        """电池充检第二阶段：发送充检进度和结果"""
        result = CD_RESULT_MAP.get(result_choice, CD_RESULT_MAP[1])

        step("1/3 上报 BMS (SOC>30，触发充检)")
        self.pub(self.m.publish_ycBMS(cif=cif, tradeID=trade_id, r_vol=400.3, r_cur=-999,
                 mode=2, soc=35, soc1=90, remainTime=16, cellMaxVol=4.09,
                 minTemp=33, maxTemp=35, m_vol=1499, m_cur=-999, cdFlag=2), "ycBMS(SOC=35)")
        self.w(interval)

        step("2/3 充检进度上报")
        for state in [1, 2, 3, 4]:
            state_names = {1: "待检测", 2: "检测中", 3: "检测中", 4: "检测中"}
            self.pub(self.m.publish_cdProgress(cif=cif, id=check_id, type=1, state=state), f"cdProgress-{state_names[state]}")
            self.w(interval)

        step("3/3 充检完成")
        self.pub(self.m.publish_cdProgress(
            cif=cif, id=check_id, type=1, state=100,
            tradeID=trade_id, vin=vin,
            beginTime=ts(-300), endTime=ts(),
            bp_r_cur=-454, beginSoC=10, endSoC=30,
            errcode=result["errcode"], errmsg=result["errmsg"]
        ), f"cdProgress-完成(errcode={result['errcode']})")
        ok(f"电池充检完成 ✓(结果: {result['errmsg']})")

    def finish_charge(self, trade_id, order_id, vin, cif=1, bsoc=10, esoc=30, reason=114):
        """结束充电流程：chargEnd → trade → 恢复空闲"""
        es, energy = rand_e()
        t1, t2, t3, t4 = ts(), ts(10), ts(200), ts(300)
        t5 = ts(random.randint(1300, 2300))

        step("1/3 结束充电")
        self.pub(self.m.publish_chargend(
            cif=cif, tradeID=trade_id, orderID=order_id, vin=vin, t1=t1, t2=t2, t3=t3, t4=t4,
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc,
            csr=reason, errCode=""
        ), "chargEnd")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=2, time=ts(), alarm=1, yx1=1, rssi=31), "yx-完成")
        self.w(1)

        step("2/3 交易上传")
        self.pub(self.m.publish_trade(
            cif=cif, tradeID=trade_id, orderID=order_id, vin=vin, t1=t1, t2=t2, t3=t3, t4=t4, t5=t5, t6='',
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc, csr=reason
        ), "trade")
        self.w(1)

        step("3/3 恢复空闲")
        self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), alarm=1, rssi=31), "yx-空闲")
        ok("充电订单已结束 ✓")

    def scenario_satisfaction_start(self, vin, cif, soc, bsoc, esoc, bat, mode="normal", bms_count=4,
                                    r_vol=None, r_cur=None, m_vol=None, m_cur=None):
        """满足度场景第一阶段：启动充电 + 发送第一条 BMS，返回(tradeID, orderID)"""
        preset = SATISFACTION_PRESETS.get(mode, SATISFACTION_PRESETS["normal"])
        bms_params = {
            "r_vol": r_vol if r_vol is not None else preset["r_vol"],
            "r_cur": r_cur if r_cur is not None else preset["r_cur"],
            "m_vol": m_vol if m_vol is not None else preset["m_vol"],
            "m_cur": m_cur if m_cur is not None else preset["m_cur"],
        }

        t = make_tid()
        es, energy = rand_e()

        step("1/? 上报空闲")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts()), "yx-空闲")
            self.w(1)

        step("2/? 车辆验证")
        self.pub(self.m.publish_carchk(cif=cif, vin=vin, vsrc='0'), "carChk")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), yx1=1, rssi=31), "yx-工作")
        self.w(1)

        step("3/? 启动状态 state 0→5")
        for s in range(6):
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID='', vin=vin, type=0, state=s, reason=0,
                batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=231.9,
                ratedKWh=74, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
                maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
                batVendor='', batNo=-1, batDate='', batChaTimes=-1,
                batProperty=-1, bmsSoftVer=''
            ), f"starting-s{s}")
            self.w(1)

        # 发送第一组满足度 BMS
        self._send_satisfaction_bms(cif, t, soc, mode, bms_params, bms_count)

        return (t, "")

    def _send_satisfaction_bms(self, cif, trade_id, soc, mode, bms_params, bms_count=1):
        """发送一条满足度 BMS 报文"""
        satisfaction = abs(bms_params["m_cur"] / bms_params["r_cur"]) * 100 if bms_params["r_cur"] != 0 else 0
        step(f"上报 BMS 数据 (满足度模式: {mode}, 满足度: {satisfaction:.1f}%)")
        self.pub(self.m.publish_ycBMS(
            cif=cif, tradeID=trade_id, r_vol=bms_params["r_vol"], r_cur=bms_params["r_cur"],
            mode=2, soc=soc, remainTime=16, cellMaxVol=4.09,
            minTemp=33, maxTemp=35, m_vol=bms_params["m_vol"], m_cur=bms_params["m_cur"]
        ), f"ycBMS-{mode}")
        ok(f"BMS 发送完成 ✓(模式: {mode}, 满足度: {satisfaction:.1f}%)")

    def send_extra_satisfaction_bms(self, cif, trade_id, soc, mode, bms_count=4):
        """追加发送其他模式的满足度 BMS 报文（充电中阶段）"""
        preset = SATISFACTION_PRESETS.get(mode, SATISFACTION_PRESETS["normal"])
        self._send_satisfaction_bms(cif, trade_id, soc, mode, preset, bms_count)

    def scenario_satisfaction_finish(self, trade_id, vin, cif, bsoc, esoc):
        """满足度场景结束阶段：YcMeas + 结束充电 + 交易 + 空闲"""
        es, energy = rand_e()
        t1, t2, t3, t4 = ts(), ts(10), ts(200), ts(300)
        t5 = ts(random.randint(1300, 2300))

        step("上报 YcMeas")
        self.pub(self.m.publish_ycMeas(tradeID=trade_id, t2=ts(), time=53,
                 energy=energy, energy1=es[0], energy2=es[1],
                 energy3=es[2], energy4=es[3]), "ycMeas")
        self.w(2)

        self.finish_charge(trade_id, "", vin, cif, bsoc, esoc)

    def scenario_identity_theft(self, vin, cif, soc=90, bsoc=20, esoc=90, vsrc=0, bat=3,
                                 rated_ah=231.9, rated_kwh=74, mode="normal"):
        """身份盗用场景"""
        if mode != "normal" and mode in IDENTITY_THEFT_PRESETS:
            preset = IDENTITY_THEFT_PRESETS[mode]
            bat = preset["bat"]
            rated_ah = preset["rated_ah"]
            rated_kwh = preset["rated_kwh"]

        t = make_tid()
        es, energy = rand_e()
        t1, t2, t3, t4 = ts(), ts(10), ts(200), ts(300)
        t5 = ts(random.randint(1300, 2300))

        step("1/7 上报空闲")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts()), "yx-空闲")
            self.w(1)

        step(f"2/7 车辆验证 (vsrc={vsrc}, vin={vin})")
        self.pub(self.m.publish_carchk(cif=cif, vin=vin, vsrc=str(vsrc)), "carChk")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), yx1=1, rssi=31), "yx-工作")
        self.w(1)

        step(f"3/7 启动状态(bat={bat}, ratedAH={rated_ah}, ratedKWh={rated_kwh})")
        for s in range(5):
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID='', vin=vin, type=0, state=s, reason=0,
                batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
                maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=rated_ah,
                ratedKWh=rated_kwh, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
                maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
                batVendor='', batNo=-1, batDate='', batChaTimes=-1,
                batProperty=-1, bmsSoftVer=''
            ), f"starting-s{s}")
            self.w(1)
        self.pub(self.m.publish_dc_starting(
            cif=cif, tradeID=t, orderID='', vin=vin, type=0, state=5, reason=0,
            batType=bat, maxAllowTemp=105, maxAllowVol=427.6, cellMaxAllowVol=4.38,
            maxAllowCur=376.1, ratedVol=345.6, batVol=336.0, ratedAH=rated_ah,
            ratedKWh=rated_kwh, batSOC=11.6, maxOutVol=500.0, minOutVol=200.0,
            maxOutCur=200.0, minOutCur=0.0, bhmMaxAllowVol=427.6, bmsPVer='V1.1',
            batVendor='', batNo=-1, batDate='', batChaTimes=-1,
            batProperty=-1, bmsSoftVer=''
        ), "starting-s5(身份比对)")
        self.w(1)

        step("4/7 上报 BMS/YX/YcMeas")
        self.pub(self.m.publish_ycBMS(cif=cif, tradeID=t, r_vol=392.3, r_cur=-511.3,
                 mode=2, soc=soc, remainTime=16, cellMaxVol=4.09,
                 minTemp=33, maxTemp=35, m_vol=220.0, m_cur=-500.0), "ycBMS")
        self.pub(self.m.publish_yx(cif=cif, status=1, time=ts(), alarm=1,
                 yx1=1, yx2=1, yx3=1, rssi=31), "yx-充电中")
        self.pub(self.m.publish_ycMeas(tradeID=t, t2=ts(), time=53,
                 energy=energy, energy1=es[0], energy2=es[1],
                 energy3=es[2], energy4=es[3]), "ycMeas")
        self.w(2)

        step("5/7 结束充电")
        self.pub(self.m.publish_chargend(
            cif=cif, tradeID=t, orderID='', vin=vin, t1=t1, t2=t2, t3=t3, t4=t4,
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc,
            csr=114, errCode=""
        ), "chargEnd")
        for _ in range(2):
            self.pub(self.m.publish_yx(cif=cif, status=2, time=ts(), alarm=1, yx1=1, rssi=31), "yx-完成")
        self.w(1)

        step("6/7 交易上传")
        self.pub(self.m.publish_trade(
            cif=cif, tradeID=t, orderID='', vin=vin, t1=t1, t2=t2, t3=t3, t4=t4, t5=t5, t6='',
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, time1=1, time2=0, time3=0, beginSoC=bsoc, endSoC=esoc, csr=114
        ), "trade")
        self.w(1)

        step("7/7 恢复空闲")
        self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), alarm=1, rssi=31), "yx-空闲")
        ok(f"身份盗用场景完成 ✓(模式: {mode})")
        return (t, "")

    def fault_error(self, cif=1, code="E07", repeat=1, interval=30):
        """故障模拟"""
        step(f"故障模拟 (errcode={code})")
        for i in range(repeat):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), error=1, errcode=code,
                     yx1=1, rssi=31), f"yx-故障({code}) [{i+1}/{repeat}]")
            if i < repeat - 1:
                self.w(interval)
        ok(f"故障模拟完成 ✓(发送 {repeat} 条)")

    def fault_estop(self, cif=1, repeat=1, interval=30):
        """急停模拟"""
        step("急停模拟 (errcode=E05)")
        for i in range(repeat):
            self.pub(self.m.publish_yx(cif=cif, status=0, time=ts(), error=1, errcode="E05",
                     yx1=1, rssi=31), f"yx-急停 [{i+1}/{repeat}]")
            if i < repeat - 1:
                self.w(interval)
        ok(f"急停模拟完成 ✓(发送 {repeat} 条)")

    def fault_upgrading(self, cif=1, repeat=1, interval=30):
        """升级中模拟"""
        step("升级中模拟(status=6)")
        for i in range(repeat):
            self.pub(self.m.publish_yx(cif=cif, status=6, time=ts(), error=0, errcode="",
                     yx1=1, rssi=31), f"yx-升级中 [{i+1}/{repeat}]")
            if i < repeat - 1:
                self.w(interval)
        ok(f"升级中模拟完成 ✓(发送 {repeat} 条)")

    def fault_start_fail(self, cif=1, vin="", reason=1, errcode="", repeat=1, interval=30):
        """启动失败模拟"""
        t = make_tid()
        step(f"启动失败模拟 (reason={reason})")
        for i in range(repeat):
            self.pub(self.m.publish_dc_starting(
                cif=cif, tradeID=t, orderID='', vin=vin, type=0, state=255,
                reason=reason, errcode=errcode
            ), f"starting-失败 [{i+1}/{repeat}]")
            if i < repeat - 1:
                self.w(interval)
        ok(f"启动失败模拟完成 ✓(发送 {repeat} 条)")

    def fault_gun_lock(self, cif=1, repeat=1, interval=30):
        """锁枪模拟"""
        step("锁枪模拟 (errcode=E71)")
        for i in range(repeat):
            self.pub(self.m.publish_yx(cif=cif, status=5, time=ts(), error=1, errcode="E71",
                     alarm=1, alarm1=1, yx1=1, yx3=1, yx4=5, yx5=2, rssi=-51,
                     linkType=0, link4g=1, linkWifi=0, linkEth=3), f"yx-锁枪 [{i+1}/{repeat}]")
            if i < repeat - 1:
                self.w(interval)
        ok(f"锁枪模拟完成 ✓(发送 {repeat} 条)")

    def fault_offline(self, cif=1, vin="", duration=30):
        """离线模拟"""
        t = make_tid()
        step("1/4 发送 bootNoti")
        self.pub(self.m.publish_bootNoti(p_ver=119, type=0, vendor="XPENG"), "bootNoti")
        self.w(1)

        step(f"2/4 断开 MQTT 连接 (离线 {duration} 秒)")
        self.client.disconnect()
        self.client.loop_stop()
        ok("MQTT 已断开")
        time.sleep(duration)

        step("3/4 重新连接 MQTT")
        self.client = self.sub.mqtt_connect()
        ok("MQTT 已重连")
        self.w(1)

        step("4/4 上报离线交易")
        es, energy = rand_e()
        self.pub(self.m.publish_ol_trade(
            cif=cif, tradeID=t, vin=vin,
            t2=ts(-duration-60), t3=ts(-duration), t4=ts(-60), t5=ts(), t6='',
            energy=energy, energy1=es[0], energy2=es[1], energy3=es[2], energy4=es[3],
            time=3, beginSoC=20, endSoC=90, csr=114
        ), "olTrade")
        ok("离线模拟完成 ✓")


# ─── 交互式菜单辅助函数 ───

VERSION = "1.0.0"


def make_check_id():
    """生成充检 ID"""
    now = datetime.datetime.now().strftime("%y%m%d%H%M%S")
    rand = str(random.randint(100000, 999999))
    return f"CJ{now}{rand}"


class QuitProgram(Exception):
    """用户输入 qq 退出程序"""
    pass


class BackToMenu(Exception):
    """用户输入 q 返回主菜单"""
    pass


def prompt(text, default=""):
    """带默认值的输入提示，输入 q 返回主菜单，输入 qq 退出程序"""
    if default:
        val = input(f"    {text} [{default}]: ").strip()
        if val.lower() == 'qq':
            raise QuitProgram()
        if val.lower() == 'q':
            raise BackToMenu()
        return val if val else str(default)
    val = input(f"    {text}: ").strip()
    if val.lower() == 'qq':
        raise QuitProgram()
    if val.lower() == 'q':
        raise BackToMenu()
    return val


def prompt_choice(options, default=1):
    """选项选择提示，输入 q 返回主菜单，输入 qq 退出程序"""
    for i, opt in enumerate(options, 1):
        marker = " (默认)" if i == default else ""
        print(f"    [{i}] {opt}{marker}")
    print(f"    [q] 返回主菜单  [qq] 退出程序")
    val = input(f"    请选择 [1-{len(options)}/q/qq]: ").strip()
    if val.lower() == 'qq':
        raise QuitProgram()
    if val.lower() == 'q':
        raise BackToMenu()
    try:
        choice = int(val) if val else default
        if 1 <= choice <= len(options):
            return choice
    except ValueError:
        pass
    return default


def interactive_mode(env="pre", pile=None, cif=1, speed=2.0):
    """交互式主菜单循环"""
    cfg = ENV_CONFIG[env]
    if pile is None:
        pile = cfg["pile"]

    # 创建 Charger 实例（整个会话复用）
    print(f"\n\033[1m\u26a1 MQTT 充电桩模拟 CLI v{VERSION}\033[0m")
    print(f"  环境: {env} | 桩: {pile} | 速度: {speed}x")

    c = Charger(pile, speed, env=env)
    c.subscribe_responses()
    ok(f"MQTT 已连接 {cfg['mqtt_ip']}:{cfg['mqtt_port']}")
    ok(f"Topic: {c.topic}")

    last_run = None
    last_run_file = ".last_run.json"
    if os.path.exists(last_run_file):
        try:
            with open(last_run_file, 'r') as f:
                last_run = json.load(f)
        except:
            pass

    repeat_choice = None  # 用于"再次执行"
    repeat_sub_choice = None  # 记住子菜单选择

    while True:
        if repeat_choice is None:
            print(f"\n\033[1m{'─'*50}\033[0m")
            print(f"  \033[1m主菜单\033[0m")
            if last_run:
                print(f"  [0] 重复上次操作 → {last_run.get('mode', '未知')}")
            print(f"  [1] 单次跑充电订单  （执行一次完整充电流程）")
            print(f"  [2] 批量跑充电订单  （循环执行多次充电流程）")
            print(f"  [3] 场景脚本       （充电小结/电池充检/满足度/身份盗用）")
            print(f"  [4] 异常状态模拟   （故障/急停/升级中）")
            print(f"  [5] 单条报文发送   （单独发送某类型 MQTT 报文）")
            print(f"  [6] 预发充值钱包   （给指定用户充值钱包余额）")
            print(f"  [7] 关闭订单       （输入订单号关闭订单）")
            print(f"  [s] 设置           （切换环境 (当前: {env})）")
            print(f"  [q] 退出")

            choice = input(f"\n  请选择 [1-7/q]: ").strip()
        else:
            choice = repeat_choice
            repeat_choice = None
            print(f"\n  \033[1;93m↻ 再次执行...\033[0m")

        if choice == "q":
            print("\n  正在断开 MQTT 连接...")
            c.client.disconnect()
            c.client.loop_stop()
            print(f"\033[92m  ✓ 已退出\033[0m\n")
            break

        if choice == "s":
            # 设置 - 切换环境
            print(f"\n  \033[1m切换环境\033[0m (当前: {env})")
            env_list = list(ENV_CONFIG.keys())
            env_choice = prompt_choice(env_list, default=env_list.index(env) + 1 if env in env_list else 1)
            new_env = env_list[env_choice - 1]
            if new_env != env:
                env = new_env
                cfg = ENV_CONFIG[env]
                pile = cfg.get("pile", pile)
                c.client.disconnect()
                c.client.loop_stop()
                c = Charger(pile, speed, env=env)
                c.subscribe_responses()
                ok(f"已切换到 {env} 环境")
                ok(f"MQTT: {cfg['mqtt_ip']}:{cfg['mqtt_port']}")
                ok(f"桩: {pile}")
            else:
                ok(f"环境未变更，仍为 {env}")
            continue

        vin = cfg.get("vin", "TEST2K0Y5JI4P6BC7")
        uid = cfg.get("uid", "8102985")
        default_pile = cfg.get("pile", "XPAC2017YS03240002")

        try:
            if choice == "1":
                # 单次跑充电订单
                print(f"\n  \033[1m单次跑充电订单\033[0m")
                mode_choice = prompt_choice(["即插即充", "扫码充电"], default=1)
                pile_no = prompt("桩编码", pile)
                vin = prompt("VIN 码", vin)
                if mode_choice == 2:
                    uid = prompt("用户 UID", uid)
                # 其他参数使用配置文件默认值
                soc, bsoc, esoc, bat = 90, 20, 90, 3

                # 桩编码变更时重新创建 Charger
                if pile_no != c.pile:
                    c = Charger(pile_no, speed, env=env)
                    pile = pile_no
                    ok(f"已切换桩: {pile_no}")

                if mode_choice == 2:
                    trade_id, order_id = c.scan_charge(vin, cif, uid, soc, bsoc, esoc, bat)
                else:
                    trade_id, order_id = c.plug_charge(vin, cif, soc, bsoc, esoc, bat)
                print(f"\n  \033[1;93m\U0001f4cb tradeID: {trade_id}  |  orderID: {order_id or '(空)'}\033[0m")

            elif choice == "2":
                # 批量跑充电订单
                print(f"\n  \033[1m批量跑充电订单\033[0m")
                mode_choice = prompt_choice(["即插即充", "扫码充电"], default=1)
                loop = int(prompt("循环次数", "1"))
                pile_no = prompt("桩编码", pile)
                vin = prompt("VIN 码", vin)
                if mode_choice == 2:
                    uid = prompt("用户 UID", uid)
                # 其他参数使用配置文件默认值
                soc, bsoc, esoc, bat = 90, 20, 90, 3

                # 桩编码变更时重新创建 Charger
                if pile_no != c.pile:
                    c = Charger(pile_no, speed, env=env)
                    pile = pile_no
                    ok(f"已切换桩: {pile_no}")

                success = 0
                fail = 0
                skip = 0
                for i in range(loop):
                    if loop > 1:
                        print(f"\n\033[1m{'='*30} 第 {i+1}/{loop} 轮 {'='*30}\033[0m")
                    try:
                        if mode_choice == 2:
                            trade_id, order_id = c.scan_charge(vin, cif, uid, soc, bsoc, esoc, bat)
                        else:
                            trade_id, order_id = c.plug_charge(vin, cif, soc, bsoc, esoc, bat)
                        print(f"\n  \033[1;93m\U0001f4cb tradeID: {trade_id}  |  orderID: {order_id or '(空)'}\033[0m")
                        success += 1
                    except Exception as e:
                        fail += 1
                        print(f"\n  \033[91m✗ 第 {i+1} 轮执行失败: {e}\033[0m")
                        retry = prompt_choice(["重试本轮", "跳过继续", "停止执行"], default=2)
                        if retry == 1:
                            try:
                                if mode_choice == 2:
                                    trade_id, order_id = c.scan_charge(vin, cif, uid, soc, bsoc, esoc, bat)
                                else:
                                    trade_id, order_id = c.plug_charge(vin, cif, soc, bsoc, esoc, bat)
                                print(f"\n  \033[1;93m\U0001f4cb tradeID: {trade_id}  |  orderID: {order_id or '(空)'}\033[0m")
                                success += 1
                                fail -= 1
                            except:
                                pass
                        elif retry == 2:
                            skip += 1
                            fail -= 1
                        elif retry == 3:
                            break
                    if i < loop - 1:
                        time.sleep(max(5 / speed, 0.05))
                print(f"\n\033[92m✓ 执行完成: 成功 {success} 轮, 失败 {fail} 轮, 跳过 {skip} 轮\033[0m")

            elif choice == "3":
                # 场景脚本
                if repeat_sub_choice is not None:
                    sc = repeat_sub_choice
                    repeat_sub_choice = None
                    print(f"\n  \033[1;93m↻ 再次执行场景脚本...\033[0m")
                else:
                    print(f"\n  \033[1m场景脚本\033[0m")
                    sc = prompt_choice([
                        "充电小结",
                        "电池充检",
                        "充电需求功率满足度",
                        "身份盗用"
                    ], default=1)

                if sc == 1:
                    # 充电小结
                    pile_no = prompt("桩编码", pile)
                    vin = prompt("VIN 码", vin)
                    uid = prompt("用户 UID", uid)
                    # 其他参数使用默认值
                    soc, bsoc, esoc, bat, reason = 90, 20, 90, 3, 114

                    # 桩编码变更时重新创建 Charger
                    if pile_no != c.pile:
                        c = Charger(pile_no, speed, env=env)
                        pile = pile_no
                        ok(f"已切换桩: {pile_no}")

                    trade_id, order_id = c.scenario_summary(vin, cif, uid, soc, bsoc, esoc, bat, reason)
                    print(f"\n  \033[1;93m\U0001f4cb tradeID: {trade_id}  |  orderID: {order_id or '(空)'}\033[0m")

                elif sc == 2:
                    # 电池充检（先跑到充电中，再输入充检参数）
                    pile_no = prompt("桩编码", pile)
                    vin = prompt("VIN 码", vin)
                    uid = prompt("用户 UID", uid)

                    # 桩编码变更时重新创建 Charger
                    if pile_no != c.pile:
                        c = Charger(pile_no, speed, env=env)
                        pile = pile_no
                        ok(f"已切换桩: {pile_no}")

                    # 第一阶段：跑充电到进行中
                    trade_id, order_id = c.scenario_battery_check_start(vin, cif, uid)

                    # 充电已到进行中，等用户输入充检参数
                    print(f"\n  \033[1;92m✓ 充电订单已到进行中，请在 APP 执行充检\033[0m")
                    input(f"\n  \033[1;93m  请在 APP 完成充检操作后，按回车继续获取充检 ID...\033[0m")

                    # 尝试通过接口自动获取充检 ID
                    auto_check_id = ""
                    if order_id:
                        try:
                            detail_url = f"https://thor.deploy-test.xiaopeng.com/api/xp-thor-operate/operate/v1/order/detail?orderNo={order_id}"
                            detail_resp = requests_http(
                                req_Url=detail_url,
                                headers={"Content-Type": "application/json; charset=UTF-8",
                                         "logan": "true", "xp-thor-skip-auth": "true"},
                                requestsType="GET")
                            if detail_resp and detail_resp.get("data"):
                                auto_check_id = detail_resp["data"].get("chargeInspection", {}).get("inspectionId", "") or ""
                                if auto_check_id:
                                    ok(f"自动获取充检 ID: {auto_check_id}")
                        except Exception as e:
                            logging.warning(f"自动获取充检 ID 失败: {e}")

                    check_id = auto_check_id
                    if auto_check_id:
                        ok(f"充检 ID: {check_id}")
                    else:
                        print(f"    \033[91m✗ 未获取到充检 ID，请确认已在 APP 执行充检\033[0m")
                        input(f"    \033[1;93m→ APP 完成充检后，按回车重新获取...\033[0m")
                        # 重新获取
                        if order_id:
                            try:
                                detail_url = f"https://thor.deploy-test.xiaopeng.com/api/xp-thor-operate/operate/v1/order/detail?orderNo={order_id}"
                                detail_resp = requests_http(
                                    req_Url=detail_url,
                                    headers={"Content-Type": "application/json; charset=UTF-8",
                                             "logan": "true", "xp-thor-skip-auth": "true"},
                                    requestsType="GET")
                                if detail_resp and detail_resp.get("data"):
                                    check_id = detail_resp["data"].get("chargeInspection", {}).get("inspectionId", "") or ""
                            except Exception as e:
                                logging.warning(f"重新获取充检 ID 失败: {e}")
                        if not check_id:
                            check_id = prompt("请手动输入充检 ID", "")
                            while not check_id:
                                print(f"    \033[91m✗ 充检 ID 不能为空\033[0m")
                                check_id = prompt("请手动输入充检 ID", "")
                        else:
                            ok(f"充检 ID: {check_id}")

                    print(f"\n    选择充检结果:")
                    result = prompt_choice([
                        "检测完成", "平台终止", "BMS 禁止充检", "BEX1 超时",
                        "暂停充电超时", "脉冲输出超时", "脉冲电流停止超时",
                        "充检时结束充电", "其他错误"
                    ], default=1)
                    interval = 2

                    # 第二阶段：发充检报文
                    c.scenario_battery_check_progress(trade_id, check_id, vin, cif, result, interval)

                    # 充检完成，等用户确认后结束充电
                    input(f"\n  \033[1;93m  充检已完成，按回车继续结束充电流程...\033[0m")
                    c.finish_charge(trade_id, order_id, vin, cif)

                elif sc == 3:
                    # 满足度
                    print(f"\n    选择满足度场景:")
                    mode_choice = prompt_choice([
                        "需求低预期高(满足度>=95%)",
                        "车桩错配",
                        "同车分流/桩故障(满足度<95%)"
                    ], default=1)
                    mode_map = {1: "normal", 2: "mismatch", 3: "shunt"}
                    mode = mode_map[mode_choice]
                    pile_no = prompt("桩编码", pile)
                    vin = prompt("VIN 码", vin)
                    uid = prompt("用户 UID", uid)
                    # 其他参数使用默认值
                    soc, bsoc, esoc, bat, bms_count = 90, 20, 90, 3, 4

                    # 桩编码变更时重新创建 Charger
                    if pile_no != c.pile:
                        c = Charger(pile_no, speed, env=env)
                        pile = pile_no
                        ok(f"已切换桩: {pile_no}")

                    trade_id, order_id = c.scenario_satisfaction_start(vin, cif, soc, bsoc, esoc, bat, mode, bms_count)
                    print(f"\n  \033[1;93m\U0001f4cb tradeID: {trade_id}  |  orderID: {order_id or '(空)'}\033[0m")

                    # 满足度场景循环：可以继续发其他场景报文或结束充电
                    while True:
                        print(f"\n  \033[1m{'─'*40}\033[0m")
                        sat_next = prompt_choice([
                            "结束充电",
                            "再发一条 BMS（需求低预期高）",
                            "再发一条 BMS（车桩错配）",
                            "再发一条 BMS（同车分流/桩故障）",
                        ], default=1)
                        if sat_next == 1:
                            break
                        else:
                            sat_mode_map = {2: "normal", 3: "mismatch", 4: "shunt"}
                            c.send_extra_satisfaction_bms(cif, trade_id, soc, sat_mode_map[sat_next], bms_count)

                    c.scenario_satisfaction_finish(trade_id, vin, cif, bsoc, esoc)

                elif sc == 4:
                    # 身份盗用
                    print(f"\n    选择身份盗用场景:")
                    mode_choice = prompt_choice([
                        "正常 (不触发告警)",
                        "电池类型不一致(触发告警+停用)",
                        "蓄电池额定容量偏差 ratedAH (触发人工核实)",
                        "蓄电池标定总能量偏差 ratedKWh (触发人工核实)"
                    ], default=1)
                    mode_map = {1: "normal", 2: "bat-type", 3: "ah-bias", 4: "kwh-bias"}
                    mode = mode_map[mode_choice]
                    pile_no = prompt("桩编码", pile)
                    vin_input = prompt("VIN 码", vin)

                    # 桩编码变更时重新创建 Charger
                    if pile_no != c.pile:
                        c = Charger(pile_no, speed, env=env)
                        pile = pile_no
                        ok(f"已切换桩: {pile_no}")

                    kwargs = {"mode": mode}
                    if mode_choice == 2:
                        bat_input = int(prompt("电池类型 (3=磷酸铁锂 6=三元锂)", "6"))
                        kwargs["bat"] = bat_input
                    if mode_choice == 3:
                        rated_ah = float(prompt("蓄电池额定容量 ratedAH", "211.9"))
                        kwargs["rated_ah"] = rated_ah
                    if mode_choice == 4:
                        rated_kwh = float(prompt("蓄电池标定总能量 ratedKWh", "83.0"))
                        kwargs["rated_kwh"] = rated_kwh
                    trade_id, order_id = c.scenario_identity_theft(vin_input, cif, **kwargs)
                    print(f"\n  \033[1;93m\U0001f4cb tradeID: {trade_id}  |  orderID: {order_id or '(空)'}\033[0m")

            elif choice == "4":
                # 异常状态模拟
                if repeat_sub_choice is not None:
                    fc = repeat_sub_choice
                    repeat_sub_choice = None
                    print(f"\n  \033[1;93m↻ 再次执行异常模拟...\033[0m")
                else:
                    print(f"\n  \033[1m异常状态模拟\033[0m")
                    fc = prompt_choice([
                    "故障 — 平台显示桩故障状态",
                    "急停 — 平台显示急停状态",
                    "升级中 — 平台显示升级中状态"
                ], default=1)

                pile_no = prompt("桩编码", pile)
                if pile_no != c.pile:
                    c = Charger(pile_no, speed, env=env)
                    pile = pile_no
                    ok(f"已切换桩: {pile_no}")

                while True:
                    if fc == 1:
                        c.fault_error(cif, "E07", 3, 5)
                    elif fc == 2:
                        c.fault_estop(cif, 3, 5)
                    elif fc == 3:
                        c.fault_upgrading(cif, 3, 5)

                    print(f"\n  \033[1m{'─'*40}\033[0m")
                    print(f"  [1] 继续发送")
                    print(f"  [2] 返回异常类型选择")
                    print(f"  [3] 返回主菜单")
                    again = input(f"  请选择 [1/2/3]: ").strip()
                    if again == "1":
                        continue
                    elif again == "2":
                        fc = prompt_choice([
                            "故障 — 平台显示桩故障状态",
                            "急停 — 平台显示急停状态",
                            "升级中 — 平台显示升级中状态"
                        ], default=fc)
                        continue
                    else:
                        break

            elif choice == "5":
                # 单条报文发送
                if repeat_sub_choice is not None:
                    mc = repeat_sub_choice
                    repeat_sub_choice = None
                    print(f"\n  \033[1;93m↻ 再次发送同类型报文...\033[0m")
                else:
                    print(f"\n  \033[1m单条报文发送\033[0m")
                    pile_no = prompt("桩编码", pile)
                    if pile_no != c.pile:
                        c = Charger(pile_no, speed, env=env)
                        pile = pile_no
                        ok(f"已切换桩: {pile_no}")
                    mc = None
                
                if mc is None:
                    msg_types = [
                    "yx — 遥信数据",
                    "ycBMS — BMS 数据",
                    "ycMeas — 计量数据",
                    "ycAnalog — 采集数据",
                    "starting — 启动状态",
                    "chargEnd — 充电结束",
                    "trade — 交易上传",
                    "carChk — 车辆验证",
                    "bootNoti — 启动通知",
                    "pileProp — 桩属性",
                    "cdProgress — 充检进度",
                    "自定义 JSON — 直接粘贴 JSON 发送",
                    ]
                    mc = prompt_choice(msg_types, default=1)
                m = c.m

                if mc == 1:  # yx
                    status = int(prompt("status (0=待机 1=工作 2=完成 6=升级中)", "0"))
                    error = int(prompt("error (0=正常 1=故障)", "0"))
                    errcode = prompt("errcode", "")
                    msg = m.publish_yx(cif=cif, status=status, time=ts(), error=error, errcode=errcode, rssi=31)
                elif mc == 2:  # ycBMS
                    tid = int(prompt("tradeID", str(make_tid())))
                    r_vol = float(prompt("r_vol (需求电压)", "392.3"))
                    r_cur = float(prompt("r_cur (需求电流)", "-511.3"))
                    m_vol = float(prompt("m_vol (输出电压)", "220.0"))
                    m_cur = float(prompt("m_cur (输出电流)", "-500.0"))
                    soc_val = int(prompt("soc", "90"))
                    msg = m.publish_ycBMS(cif=cif, tradeID=tid, r_vol=r_vol, r_cur=r_cur, m_vol=m_vol, m_cur=m_cur, soc=soc_val)
                elif mc == 3:  # ycMeas
                    tid = int(prompt("tradeID", str(make_tid())))
                    energy = float(prompt("energy (总电量 KWh)", "20.0"))
                    msg = m.publish_ycMeas(tradeID=tid, t2=ts(), time=53, energy=energy)
                elif mc == 4:  # ycAnalog
                    msg = m.publish_ycAnalog()
                elif mc == 5:  # starting
                    tid = int(prompt("tradeID", str(make_tid())))
                    v = prompt("VIN", vin)
                    state = int(prompt("state (0-5, 255=失败)", "5"))
                    msg = m.publish_dc_starting(cif=cif, tradeID=tid, vin=v, state=state)
                elif mc == 6:  # chargEnd
                    tid = int(prompt("tradeID", str(make_tid())))
                    v = prompt("VIN", vin)
                    msg = m.publish_chargend(cif=cif, tradeID=tid, vin=v)
                elif mc == 7:  # trade
                    tid = int(prompt("tradeID", str(make_tid())))
                    v = prompt("VIN", vin)
                    msg = m.publish_trade(cif=cif, tradeID=tid, vin=v)
                elif mc == 8:  # carChk
                    v = prompt("VIN", vin)
                    vsrc = prompt("vsrc (0=小鹏 1=其他)", "0")
                    msg = m.publish_carchk(cif=cif, vin=v, vsrc=vsrc)
                elif mc == 9:  # bootNoti
                    p_ver = int(prompt("协议版本号", "119"))
                    pile_type = int(prompt("桩类型(0=直流 1=交流)", "0"))
                    msg = m.publish_bootNoti(p_ver=p_ver, type=pile_type)
                elif mc == 10:  # pileProp
                    cd_en = int(prompt("cdEn (1=支持充检)", "1"))
                    msg = m.publish_pileProp(cdEn=cd_en)
                elif mc == 11:  # cdProgress
                    cd_id = prompt("充检 ID", make_check_id())
                    state = int(prompt("state (1=待检 2-4=检测中 100=完成)", "1"))
                    msg = m.publish_cdProgress(cif=cif, id=cd_id, state=state)
                elif mc == 12:  # 自定义 JSON
                    raw = prompt("请粘贴 JSON 字符串", "")
                    try:
                        json.loads(raw)  # 校验
                        msg = raw
                    except json.JSONDecodeError:
                        print("    \033[91m✗ 无效 JSON 格式\033[0m")
                        continue
                else:
                    continue

                repeat = int(prompt("发送次数", "1"))
                for i in range(repeat):
                    c.pub(msg, f"单条发送[{i+1}/{repeat}]")
                    if i < repeat - 1:
                        interval = int(prompt("发送间隔(秒)", "1") if i == 0 else "1")
                        c.w(interval)
                print(f"\n    \033[92m完整报文:\033[0m {msg}")

            elif choice == "6":
                # 预发充值钱包
                print(f"\n  \033[1m预发充值钱包\033[0m")
                wallet_uid = prompt("用户 UID", uid)
                amount = int(prompt("充值金额（分，默认 9000000 = 9万元）", "9000000"))
                
                wallet_url = f"https://quali.deploy-test.xiaopeng.com/api/v1/wallet/{wallet_uid}/update"
                wallet_body = json.dumps({"total": amount, "valid": amount, "freeze": 0})
                
                step(f"充值钱包(UID={wallet_uid}, 金额={amount}分)")
                resp = requests_http(
                    req_Url=wallet_url,
                    headers={"Content-Type": "application/json"},
                    requestsType="POST",
                    requestsBody=wallet_body)
                if resp:
                    ok(f"充值成功 ✓ 响应: {json.dumps(resp, ensure_ascii=False)}")
                else:
                    print(f"    \033[91m✗ 充值失败\033[0m")

            elif choice == "7":
                # 关闭订单
                print(f"\n  \033[1m关闭订单\033[0m")
                order_no = prompt("订单号", "")
                while not order_no:
                    print("    \033[91m\u2717 订单号不能为空\033[0m")
                    order_no = prompt("订单号", "")
                
                close_base = "https://thor.deploy-test.xiaopeng.com" if env == "pre" else "http://thor.test.xiaopeng.local"
                close_url = f"{close_base}/api/xp-thor-operate/operate/v1/order/close"
                close_data = {"orderNo": order_no, "closeReason": "充电量过高", "closeRemark": "1"}
                
                step(f"关闭订单 (orderNo={order_no})")
                import requests as req_lib
                try:
                    resp = req_lib.post(
                        url=close_url,
                        json=close_data,
                        headers={"Content-Type": "application/json", "logan": "test", "xp-thor-skip-auth": "true", "xp-thor-user-id": "8102985"},
                        timeout=60,
                        verify=False)
                    resp_json = resp.json()
                    print(f"    响应: {json.dumps(resp_json, ensure_ascii=False)}")
                    if resp_json.get("code") == 0:
                        ok("关闭成功 \u2713")
                    else:
                        print(f"    \033[91m\u2717 关闭失败: {resp_json.get('msg', '')}\033[0m")
                except Exception as e:
                    print(f"    \033[91m\u2717 请求失败: {e}\033[0m")

            else:
                print("    \033[91m✗ 无效选择，请重新输入\033[0m")

        except KeyboardInterrupt:
            print("\n\n  已中断，返回主菜单...")
            continue
        except BackToMenu:
            print("\n  返回主菜单...")
            continue
        except QuitProgram:
            print("\n  正在断开 MQTT 连接...")
            c.client.disconnect()
            c.client.loop_stop()
            print(f"\033[92m  ✓ 已退出\033[0m\n")
            break
        except Exception as e:
            print(f"\n  \033[91m✗ 执行出错: {e}\033[0m")
            continue

        # 执行完成后提示
        print(f"\n  \033[1m{'─'*40}\033[0m")
        print(f"  [1] 再次执行同样的操作")
        print(f"  [2] 返回上一级菜单")
        print(f"  [3] 返回主菜单")
        print(f"  [q] 退出程序")
        again = input(f"  请选择 [1/2/3/q]: ").strip()
        if again == "1":
            repeat_choice = choice
            if choice == "3":
                repeat_sub_choice = sc
            elif choice == "4":
                repeat_sub_choice = fc
            elif choice == "5":
                repeat_sub_choice = mc
        elif again == "2":
            # 返回上一级：场景脚本/异常模拟/单条报文回到子菜单，其他回到主菜单
            if choice in ("3", "4", "5"):
                repeat_choice = choice  # 回到对应子菜单，但不记住子选择
        elif again.lower() in ("q", "qq"):
            print("\n  正在断开 MQTT 连接...")
            c.client.disconnect()
            c.client.loop_stop()
            print(f"\033[92m  ✓ 已退出\033[0m\n")
            break
        # 其他输入（包括 3 和回车）返回主菜单


def generate_default_config(path="config.yaml"):
    """生成默认配置文件"""
    template = '''# MQTT 充电桩模拟 CLI 配置文件
# 详细说明请参考 README.md

environments:
  pre:
    mqtt_ip: "47.96.240.241"
    mqtt_port: 12883
    mqtt_user: "charge-mqtt"
    mqtt_pwd: "vTZLRlmlDJiR"
    public_pile: "XPeng_10002_Charge"
    url_equip: "https://thor.deploy-test.xiaopeng.com/api/xp-thor-asset/asset/equip/search"
    url_order: "https://xmart.deploy-test.xiaopeng.com/biz/v5/chargeOrder/chargeOrderV2"
    pile: "XPAC2017YS03240002"
    vin: "TEST2K0Y5JI4P6BC7"
    uid: "8102985"
  test:
    mqtt_ip: "47.96.240.241"
    mqtt_port: 12883
    mqtt_user: "charge-private-mqtt"
    mqtt_pwd: "0LZVRlmlD88Y"
    public_pile: "XPeng_TEST_Charge"
    url_equip: "http://thor.test.xiaopeng.local/api/xp-thor-asset/asset/equip/search"
    url_order: "https://10.0.13.28:8553/biz/v5/chargeOrder/chargeOrderV2"
    pile: "559847003"
    vin: "TESTNUYCXPKWVTIZF"
    uid: "1160057"

defaults:
  env: "pre"
  cif: 1
  speed: 2.0
  soc: 90
  bsoc: 20
  esoc: 90
  bat: 3
  rated_ah: 231.9
  rated_kwh: 74

battery:
  maxAllowTemp: 105
  maxAllowVol: 427.6
  cellMaxAllowVol: 4.38
  maxAllowCur: 376.1
  ratedVol: 345.6
  batVol: 336.0
  maxOutVol: 500.0
  minOutVol: 200.0
  maxOutCur: 200.0
  minOutCur: 0.0
  bhmMaxAllowVol: 427.6
'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(template)


def setup_logging():
    """设置日志"""
    log_dir = "./logs/"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s -> %(message)s'))
    logging.getLogger().addHandler(file_handler)
    return log_file


def cmd_run(args):
    """执行充电订单（子命令 run）"""
    cfg = ENV_CONFIG[args.env]
    pile = args.pile or cfg["pile"]
    vin = args.vin or cfg["vin"]
    uid = args.uid or cfg["uid"]

    c = Charger(pile, args.speed, env=args.env)
    ok(f"MQTT 已连接 {cfg['mqtt_ip']}:{cfg['mqtt_port']}")

    for i in range(args.loop):
        if args.loop > 1:
            print(f"\n\033[1m{'='*30} 第 {i+1}/{args.loop} 轮 {'='*30}\033[0m")
        if args.mode == "scan":
            tid, oid = c.scan_charge(vin, args.cif, uid, args.soc, args.bsoc, args.esoc, args.bat)
        else:
            tid, oid = c.plug_charge(vin, args.cif, args.soc, args.bsoc, args.esoc, args.bat)
        print(f"\n  \033[1;93m\U0001f4cb tradeID: {tid}  |  orderID: {oid or '(空)'}\033[0m")
        if i < args.loop - 1:
            time.sleep(max(5 / args.speed, 0.05))

    print(f"\n\033[92m✓ 全部完成 ({args.loop} 轮)\033[0m\n")
    c.client.disconnect()
    c.client.loop_stop()


def cmd_scenario(args):
    """执行场景脚本（子命令 scenario）"""
    cfg = ENV_CONFIG[args.env]
    pile = args.pile or cfg["pile"]
    vin = args.vin or cfg["vin"]
    uid = args.uid or cfg["uid"]

    c = Charger(pile, args.speed, env=args.env)
    ok(f"MQTT 已连接 {cfg['mqtt_ip']}:{cfg['mqtt_port']}")

    if args.scenario == "summary":
        tid, oid = c.scenario_summary(vin, args.cif, uid, args.soc, args.bsoc, args.esoc, args.bat, args.reason)
        print(f"\n  \033[1;93m\U0001f4cb tradeID: {tid}  |  orderID: {oid or '(空)'}\033[0m")

    elif args.scenario == "battery-check":
        tid, oid = c.scenario_battery_check_start(vin, args.cif, uid)
        print(f"\n  \033[93m→ 充电已到进行中，请在 APP 执行充检后重新运行充检进度命令\033[0m")
        print(f"  \033[93m  python mqtt_cli.py scenario battery-check-progress --pile {pile} --trade-id {tid} --vin {vin}\033[0m")

    elif args.scenario == "battery-check-progress":
        check_id = args.check_id or make_check_id()
        c.scenario_battery_check_progress(args.trade_id, check_id, vin, args.cif, args.result, 2)
        if args.finish:
            c.finish_charge(args.trade_id, "", vin, args.cif)

    elif args.scenario == "satisfaction":
        modes = [m.strip() for m in args.mode.split(",")]
        first_mode = modes[0]
        tid, oid = c.scenario_satisfaction_start(vin, args.cif, args.soc, args.bsoc, args.esoc, args.bat, first_mode, args.bms_count)
        print(f"\n  \033[1;93m\U0001f4cb tradeID: {tid}  |  orderID: {oid or '(空)'}\033[0m")

        # 发送预设的额外模式
        for extra_mode in modes[1:]:
            c.send_extra_satisfaction_bms(args.cif, tid, args.soc, extra_mode, args.bms_count)

        # 询问用户是否继续发其他模式
        while True:
            print(f"\n  \033[1m{'─'*40}\033[0m")
            print(f"  [1] 结束充电")
            print(f"  [2] 再发一条 BMS（需求低预期高）")
            print(f"  [3] 再发一条 BMS（车桩错配）")
            print(f"  [4] 再发一条 BMS（同车分流/桩故障）")
            sat_next = input(f"  请选择 [1-4]: ").strip()
            if sat_next == "1" or sat_next == "":
                break
            elif sat_next == "2":
                c.send_extra_satisfaction_bms(args.cif, tid, args.soc, "normal", args.bms_count)
            elif sat_next == "3":
                c.send_extra_satisfaction_bms(args.cif, tid, args.soc, "mismatch", args.bms_count)
            elif sat_next == "4":
                c.send_extra_satisfaction_bms(args.cif, tid, args.soc, "shunt", args.bms_count)

        c.scenario_satisfaction_finish(tid, vin, args.cif, args.bsoc, args.esoc)

    elif args.scenario == "identity-theft":
        tid, oid = c.scenario_identity_theft(vin, args.cif, vsrc=args.vsrc, mode=args.mode)
        print(f"\n  \033[1;93m\U0001f4cb tradeID: {tid}  |  orderID: {oid or '(空)'}\033[0m")

    c.client.disconnect()
    c.client.loop_stop()


def cmd_fault(args):
    """执行异常模拟（子命令 fault）"""
    cfg = ENV_CONFIG[args.env]
    pile = args.pile or cfg["pile"]
    vin = args.vin or cfg["vin"]

    c = Charger(pile, args.speed, env=args.env)
    ok(f"MQTT 已连接 {cfg['mqtt_ip']}:{cfg['mqtt_port']}")

    if args.fault == "error":
        c.fault_error(args.cif, args.code, args.repeat, args.interval)
    elif args.fault == "estop":
        c.fault_estop(args.cif, args.repeat, args.interval)
    elif args.fault == "upgrading":
        c.fault_upgrading(args.cif, args.repeat, args.interval)
    elif args.fault == "start-fail":
        c.fault_start_fail(args.cif, vin, args.reason, args.errcode, args.repeat, args.interval)
    elif args.fault == "gun-lock":
        c.fault_gun_lock(args.cif, args.repeat, args.interval)
    elif args.fault == "offline":
        c.fault_offline(args.cif, vin, args.duration)

    c.client.disconnect()
    c.client.loop_stop()


def cmd_send(args):
    """发送单条报文（子命令 send）"""
    cfg = ENV_CONFIG[args.env]
    pile = args.pile or cfg["pile"]

    c = Charger(pile, args.speed, env=args.env)
    ok(f"MQTT 已连接 {cfg['mqtt_ip']}:{cfg['mqtt_port']}")

    try:
        json.loads(args.json)
    except json.JSONDecodeError:
        print(f"\033[91m✗ 无效 JSON: {args.json}\033[0m")
        sys.exit(1)

    for i in range(args.repeat):
        c.pub(args.json, f"发送[{i+1}/{args.repeat}]")
        if i < args.repeat - 1:
            c.w(args.interval)

    print(f"\n\033[92m✓ 发送完成 ({args.repeat} 条)\033[0m")
    c.client.disconnect()
    c.client.loop_stop()


def main():
    # MCP 模式不做交互式检查
    if os.environ.get("MQTT_CLI_MCP_MODE") != "1":
        if not os.path.exists("config.yaml"):
            print("  \033[93m⚠ 未找到 config.yaml 配置文件\033[0m")
            try:
                create = input("  是否生成默认配置文件? [Y/n]: ").strip().lower()
                if create != 'n':
                    generate_default_config()
                    print("  \033[92m✓ 已生成 config.yaml\033[0m")
            except EOFError:
                pass

    log_file = setup_logging()
    print(f"  \033[92m✓ 日志文件: {log_file}\033[0m")

    # ─── 主解析器 ───
    p = argparse.ArgumentParser(
        description="MQTT 充电桩模拟 CLI — 支持交互式菜单和命令行直接调用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python mqtt_cli.py                                          # 交互式菜单
  python mqtt_cli.py run plug --pile XPAC2017YS03240002       # 即插即充
  python mqtt_cli.py run scan --pile XPAC2017YS03240002 --uid 8102985  # 扫码充电
  python mqtt_cli.py run plug --loop 10                       # 批量跑 10 轮
  python mqtt_cli.py scenario summary --pile XPAC2017YS03240002 --uid 8102985
  python mqtt_cli.py scenario satisfaction --mode shunt
  python mqtt_cli.py scenario identity-theft --mode bat-type
  python mqtt_cli.py fault error --code E07
  python mqtt_cli.py fault estop
  python mqtt_cli.py send --json '{"msg":"yx","cif":1,"status":0}'
        """)
    p.add_argument("--env", default="pre", help="环境 (pre/test)")
    p.add_argument("--pile", default=None, help="桩编码")
    p.add_argument("--vin", default=None, help="车辆VIN")
    p.add_argument("--uid", default=None, help="用户UID")
    p.add_argument("--cif", type=int, default=1, help="充电接口")
    p.add_argument("--speed", type=float, default=2.0, help="速度倍数")
    p.add_argument("--version", action="version", version=f"mqtt-cli v{VERSION}")

    sub = p.add_subparsers(dest="command", help="子命令")

    # ─── run 子命令 ───
    run_p = sub.add_parser("run", help="跑充电订单")
    run_p.add_argument("mode", choices=["plug", "scan"], help="充电模式 (plug=即插即充, scan=扫码)")
    run_p.add_argument("--loop", type=int, default=1, help="循环次数")
    run_p.add_argument("--soc", type=int, default=90, help="BMS SOC")
    run_p.add_argument("--bsoc", type=int, default=20, help="开始SOC")
    run_p.add_argument("--esoc", type=int, default=90, help="结束SOC")
    run_p.add_argument("--bat", type=int, default=3, help="电池类型 (3=磷酸铁锂 6=三元锂)")

    # ─── scenario 子命令 ───
    sc_p = sub.add_parser("scenario", help="场景脚本")
    sc_p.add_argument("scenario", choices=["summary", "battery-check", "battery-check-progress", "satisfaction", "identity-theft"], help="场景类型")
    sc_p.add_argument("--mode", default="normal", help="场景模式，满足度支持逗号分隔多个模式如 normal,mismatch,shunt")
    sc_p.add_argument("--vsrc", type=int, default=0, help="车辆来源 (0=小鹏 1=其他)")
    sc_p.add_argument("--reason", type=int, default=114, help="充电结束原因码 CSR")
    sc_p.add_argument("--soc", type=int, default=90)
    sc_p.add_argument("--bsoc", type=int, default=20)
    sc_p.add_argument("--esoc", type=int, default=90)
    sc_p.add_argument("--bat", type=int, default=3)
    sc_p.add_argument("--bms-count", type=int, default=4, help="BMS 报文发送次数")
    sc_p.add_argument("--trade-id", type=int, default=0, help="tradeID (充检进度用)")
    sc_p.add_argument("--check-id", default=None, help="充检 ID")
    sc_p.add_argument("--result", type=int, default=1, help="充检结果 (1=完成 2=平台终止 ...)")
    sc_p.add_argument("--finish", action="store_true", help="充检后自动结束充电")

    # ─── fault 子命令 ───
    ft_p = sub.add_parser("fault", help="异常状态模拟")
    ft_p.add_argument("fault", choices=["error", "estop", "upgrading", "start-fail", "gun-lock", "offline"], help="异常类型")
    ft_p.add_argument("--code", default="E07", help="故障码")
    ft_p.add_argument("--reason", type=int, default=1, help="启动失败原因码")
    ft_p.add_argument("--errcode", default="", help="启动失败故障编码")
    ft_p.add_argument("--duration", type=int, default=30, help="离线时长(秒)")
    ft_p.add_argument("--repeat", type=int, default=1, help="发送次数")
    ft_p.add_argument("--interval", type=int, default=30, help="发送间隔(秒)")

    # ─── send 子命令 ───
    sd_p = sub.add_parser("send", help="发送单条报文")
    sd_p.add_argument("--json", required=True, help="JSON 报文字符串")
    sd_p.add_argument("--repeat", type=int, default=1, help="发送次数")
    sd_p.add_argument("--interval", type=int, default=1, help="发送间隔(秒)")

    args = p.parse_args()

    # 环境名校验
    if args.env not in ENV_CONFIG:
        print(f"\033[91m✗ 错误: 未知环境 '{args.env}'，可用环境: {', '.join(ENV_CONFIG.keys())}\033[0m")
        sys.exit(1)

    # 无子命令 → 交互式菜单
    if args.command is None:
        interactive_mode(args.env, args.pile, args.cif, args.speed)
        return

    # 有子命令 → 直接执行
    print(f"\n\033[1m\u26a1 MQTT 充电桩模拟 CLI v{VERSION}\033[0m")
    print(f"  环境: {args.env} | 命令: {args.command}")

    if args.command == "run":
        cmd_run(args)
    elif args.command == "scenario":
        cmd_scenario(args)
    elif args.command == "fault":
        cmd_fault(args)
    elif args.command == "send":
        cmd_send(args)


if __name__ == "__main__":
    main()
