# -*- coding: utf-8 -*-
"""
飞书机器人 — MQTT 充电桩模拟工具
在飞书群里 @机器人 + 自然语言指令，即可执行充电桩模拟操作。

使用方法：
1. 在飞书开放平台创建机器人，获取 App ID 和 App Secret
2. 配置环境变量或修改下方 FEISHU_APP_ID / FEISHU_APP_SECRET
3. 运行: python feishu_bot.py
4. 将公网地址配置到飞书机器人的事件订阅 URL: http://<your-ip>:9800/feishu/webhook
"""
import json
import re
import os
import io
import logging
import hashlib
import time
from contextlib import redirect_stdout, redirect_stderr
from flask import Flask, request, jsonify
import requests as req_lib

# ─── 配置 ───
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
BOT_PORT = int(os.environ.get("BOT_PORT", "9800"))

# 设置 MCP 模式，避免 mqtt_cli 的 print 干扰
os.environ["MQTT_CLI_MCP_MODE"] = "1"

logging.basicConfig(level=logging.INFO, format='%(asctime)s [飞书Bot] %(message)s')
logger = logging.getLogger(__name__)

# 复用现有模块
from mqtt_cli import ENV_CONFIG, Charger

app = Flask(__name__)

# ─── 飞书 API ───

_token_cache = {"token": "", "expire": 0}


def get_tenant_token():
    """获取飞书 tenant_access_token"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expire"]:
        return _token_cache["token"]

    resp = req_lib.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=10
    )
    data = resp.json()
    token = data.get("tenant_access_token", "")
    _token_cache["token"] = token
    _token_cache["expire"] = now + data.get("expire", 7200) - 300
    return token


def reply_message(message_id, text):
    """回复飞书消息"""
    token = get_tenant_token()
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
    body = {
        "content": json.dumps({"text": text}),
        "msg_type": "text"
    }
    try:
        resp = req_lib.post(url, json=body, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }, timeout=30)
        logger.info(f"回复消息: {resp.status_code}")
    except Exception as e:
        logger.error(f"回复消息失败: {e}")


def send_message(chat_id, text):
    """主动发送消息到群"""
    token = get_tenant_token()
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    body = {
        "receive_id": chat_id,
        "content": json.dumps({"text": text}),
        "msg_type": "text"
    }
    try:
        resp = req_lib.post(url, json=body, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }, params={"receive_id_type": "chat_id"}, timeout=30)
        logger.info(f"发送消息: {resp.status_code}")
    except Exception as e:
        logger.error(f"发送消息失败: {e}")


# ─── 指令解析与执行 ───

def capture_output(func, *args, **kwargs):
    """捕获函数的 print 输出"""
    buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err_buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


def execute_charger(action, env="pre", pile=None, vin=None, uid=None, **kwargs):
    """执行充电桩操作，返回结果文本"""
    cfg = ENV_CONFIG.get(env, ENV_CONFIG["pre"])
    pile = pile or cfg["pile"]
    vin = vin or cfg["vin"]
    uid = uid or cfg["uid"]

    c = Charger(pile, speed=2.0, env=env)
    try:
        if action == "plug_charge":
            (tid, oid), _ = capture_output(c.plug_charge, vin, 1, 90, 20, 90, 3)
            return f"✅ 即插即充完成\n桩: {pile}\nVIN: {vin}\ntradeID: {tid}\norderID: {oid or '(空)'}"

        elif action == "scan_charge":
            (tid, oid), _ = capture_output(c.scan_charge, vin, 1, uid, 90, 20, 90, 3)
            return f"✅ 扫码充电完成\n桩: {pile}\nVIN: {vin}\nUID: {uid}\ntradeID: {tid}\norderID: {oid or '(空)'}"

        elif action == "summary":
            (tid, oid), _ = capture_output(c.scenario_summary, vin, 1, uid, 90, 20, 90, 3, 114)
            return f"✅ 充电小结完成\n桩: {pile}\ntradeID: {tid}\norderID: {oid or '(空)'}"

        elif action == "satisfaction":
            mode = kwargs.get("mode", "normal")
            (tid, oid), _ = capture_output(c.scenario_satisfaction_start, vin, 1, 90, 20, 90, 3, mode, 4)
            capture_output(c.scenario_satisfaction_finish, tid, vin, 1, 20, 90)
            return f"✅ 满足度场景完成 (模式: {mode})\n桩: {pile}\ntradeID: {tid}"

        elif action == "identity_theft":
            mode = kwargs.get("mode", "normal")
            (tid, oid), _ = capture_output(c.scenario_identity_theft, vin, 1, mode=mode)
            return f"✅ 身份盗用场景完成 (模式: {mode})\n桩: {pile}\ntradeID: {tid}"

        elif action == "fault_error":
            code = kwargs.get("code", "E07")
            capture_output(c.fault_error, 1, code)
            return f"✅ 故障模拟完成 (errcode={code})\n桩: {pile}"

        elif action == "fault_estop":
            capture_output(c.fault_estop, 1)
            return f"✅ 急停模拟完成 (E05)\n桩: {pile}"

        elif action == "fault_upgrading":
            capture_output(c.fault_upgrading, 1)
            return f"✅ 升级中模拟完成 (status=6)\n桩: {pile}"

        elif action == "fault_start_fail":
            capture_output(c.fault_start_fail, 1, vin)
            return f"✅ 启动失败模拟完成\n桩: {pile}"

        elif action == "fault_gun_lock":
            capture_output(c.fault_gun_lock, 1)
            return f"✅ 锁枪模拟完成 (E71)\n桩: {pile}"

        else:
            return f"❌ 未知操作: {action}"

    except Exception as e:
        return f"❌ 执行失败: {str(e)}"
    finally:
        try:
            c.client.disconnect()
            c.client.loop_stop()
        except:
            pass


# ─── 自然语言解析 ───

# 桩编号正则
PILE_RE = re.compile(r'(?:桩|桩编[码号]|pile)\s*[:：]?\s*([A-Za-z0-9]+)', re.IGNORECASE)
# VIN 正则
VIN_RE = re.compile(r'(?:vin|VIN)\s*[:：]?\s*([A-Za-z0-9]+)', re.IGNORECASE)
# UID 正则
UID_RE = re.compile(r'(?:uid|UID)\s*[:：]?\s*(\d+)', re.IGNORECASE)
# 环境正则
ENV_RE = re.compile(r'(?:环境|env)\s*[:：]?\s*(pre|test)', re.IGNORECASE)
# 独立桩编号（XPAC/XPDC 开头或纯数字9位以上）
PILE_STANDALONE_RE = re.compile(r'\b(XP[A-Z]{2}\w{10,}|\d{9,})\b')


def extract_params(text):
    """从文本中提取参数"""
    params = {}

    m = ENV_RE.search(text)
    if m:
        params["env"] = m.group(1).lower()

    m = PILE_RE.search(text)
    if m:
        params["pile"] = m.group(1)
    else:
        m = PILE_STANDALONE_RE.search(text)
        if m:
            params["pile"] = m.group(1)

    m = VIN_RE.search(text)
    if m:
        params["vin"] = m.group(1)

    m = UID_RE.search(text)
    if m:
        params["uid"] = m.group(1)

    return params


def parse_command(text):
    """
    解析自然语言指令，返回 (action, params) 或 (None, help_text)
    """
    text = text.strip()
    params = extract_params(text)

    # 即插即充
    if re.search(r'即插即充|plug.?charge', text, re.IGNORECASE):
        return "plug_charge", params

    # 扫码充电
    if re.search(r'扫码充电|scan.?charge', text, re.IGNORECASE):
        return "scan_charge", params

    # 充电小结
    if re.search(r'充电小结|summary', text, re.IGNORECASE):
        return "summary", params

    # 满足度
    if re.search(r'满足度|satisfaction', text, re.IGNORECASE):
        if re.search(r'错配|mismatch', text, re.IGNORECASE):
            params["mode"] = "mismatch"
        elif re.search(r'分流|shunt', text, re.IGNORECASE):
            params["mode"] = "shunt"
        else:
            params["mode"] = "normal"
        return "satisfaction", params

    # 身份盗用
    if re.search(r'身份盗用|identity.?theft', text, re.IGNORECASE):
        if re.search(r'电池类型|bat.?type', text, re.IGNORECASE):
            params["mode"] = "bat-type"
        elif re.search(r'容量|ah.?bias|ratedAH', text, re.IGNORECASE):
            params["mode"] = "ah-bias"
        elif re.search(r'能量|kwh.?bias|ratedKWh', text, re.IGNORECASE):
            params["mode"] = "kwh-bias"
        else:
            params["mode"] = "normal"
        return "identity_theft", params

    # 故障
    if re.search(r'故障|fault.?error', text, re.IGNORECASE):
        code_m = re.search(r'E\d+', text)
        if code_m:
            params["code"] = code_m.group(0)
        return "fault_error", params

    # 急停
    if re.search(r'急停|estop', text, re.IGNORECASE):
        return "fault_estop", params

    # 升级
    if re.search(r'升级|upgrading', text, re.IGNORECASE):
        return "fault_upgrading", params

    # 启动失败
    if re.search(r'启动失败|start.?fail', text, re.IGNORECASE):
        return "fault_start_fail", params

    # 锁枪
    if re.search(r'锁枪|gun.?lock', text, re.IGNORECASE):
        return "fault_gun_lock", params

    # 帮助
    if re.search(r'帮助|help|菜单|指令|怎么用', text, re.IGNORECASE):
        return None, None

    return None, None


HELP_TEXT = """📋 充电桩模拟机器人 — 指令说明

🔌 充电流程:
  • 即插即充
  • 扫码充电 UID 8102985
  • 充电小结

🎯 场景模拟:
  • 满足度 正常/车桩错配/分流
  • 身份盗用 正常/电池类型不一致/容量偏差/能量偏差

⚠️ 异常模拟:
  • 故障 E07
  • 急停
  • 升级中
  • 启动失败
  • 锁枪

💡 可选参数（加在指令后面）:
  • 桩 XPAC2017YS03240002
  • VIN TEST2K0Y5JI4P6BC7
  • UID 8102985
  • 环境 pre/test

示例: 即插即充 桩 XPAC2017YS03240002 环境 pre"""


# ─── 去重（飞书可能重复推送） ───

_processed_events = {}


def is_duplicate(event_id):
    """检查事件是否重复"""
    now = time.time()
    # 清理 5 分钟前的记录
    expired = [k for k, v in _processed_events.items() if now - v > 300]
    for k in expired:
        del _processed_events[k]

    if event_id in _processed_events:
        return True
    _processed_events[event_id] = now
    return False


# ─── Flask 路由 ───

@app.route("/feishu/webhook", methods=["POST"])
def feishu_webhook():
    """飞书事件回调"""
    data = request.json or {}

    # URL 验证（飞书配置回调时会发送）
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    # 事件 v2.0 格式
    header = data.get("header", {})
    event = data.get("event", {})
    event_id = header.get("event_id", "")
    event_type = header.get("event_type", "")

    # 去重
    if event_id and is_duplicate(event_id):
        return jsonify({"code": 0})

    # 只处理消息事件
    if event_type == "im.message.receive_v1":
        message = event.get("message", {})
        msg_type = message.get("message_type", "")
        message_id = message.get("message_id", "")
        chat_id = message.get("chat_id", "")

        # 只处理文本消息
        if msg_type != "text":
            reply_message(message_id, "⚠️ 暂时只支持文本指令，请发送文字消息。")
            return jsonify({"code": 0})

        # 解析消息内容
        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "").strip()

        # 去掉 @机器人 的部分
        text = re.sub(r'@_user_\d+', '', text).strip()
        text = re.sub(r'@\S+', '', text).strip()

        if not text:
            reply_message(message_id, HELP_TEXT)
            return jsonify({"code": 0})

        logger.info(f"收到指令: {text}")

        # 解析指令
        action, params = parse_command(text)

        if action is None:
            reply_message(message_id, HELP_TEXT)
            return jsonify({"code": 0})

        # 先回复"执行中"
        reply_message(message_id, f"⏳ 正在执行: {text}...")

        # 执行
        result = execute_charger(action, **params)
        reply_message(message_id, result)

        logger.info(f"执行完成: {action} -> {result[:100]}")

    return jsonify({"code": 0})


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "mqtt-charger-feishu-bot"})


# ─── 启动 ───

if __name__ == "__main__":
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("=" * 50)
        print("⚠️  请设置环境变量:")
        print("  FEISHU_APP_ID=你的飞书应用 App ID")
        print("  FEISHU_APP_SECRET=你的飞书应用 App Secret")
        print("  FEISHU_VERIFICATION_TOKEN=事件订阅的 Verification Token")
        print("")
        print("或者直接修改 feishu_bot.py 顶部的配置")
        print("=" * 50)
        print("")

    print(f"🤖 飞书充电桩模拟机器人启动中...")
    print(f"   端口: {BOT_PORT}")
    print(f"   回调地址: http://<your-ip>:{BOT_PORT}/feishu/webhook")
    print(f"   健康检查: http://localhost:{BOT_PORT}/health")
    app.run(host="0.0.0.0", port=BOT_PORT, debug=False)
