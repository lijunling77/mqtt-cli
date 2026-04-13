# -*- coding: utf-8 -*-
"""
MQTT 充电桩模拟 MCP Server
使用 stdin/stdout JSON-RPC 协议与 Kiro 通信
"""
import json
import sys
import os
import io
import logging
from contextlib import redirect_stdout, redirect_stderr

# 禁止 mqtt_cli 的 print 输出到 stdout（会干扰 MCP 协议）
# 先设置环境变量标记为 MCP 模式
os.environ["MQTT_CLI_MCP_MODE"] = "1"

# 重定向 stderr 用于日志，stdout 用于 MCP 协议
logging.basicConfig(level=logging.INFO, format='%(asctime)s -> %(message)s', stream=sys.stderr)

# 复用现有模块
from mqtt_cli import (
    ENV_CONFIG, Charger, make_tid, make_check_id, ts, rand_e,
    SATISFACTION_PRESETS, IDENTITY_THEFT_PRESETS, CD_RESULT_MAP,
    SUMMARY_BMS_SEQUENCE
)


def capture_output(func, *args, **kwargs):
    """捕获函数的 print 输出，不让它污染 stdout"""
    buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err_buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


# ─── Tool 定义 ───

TOOLS = [
    {
        "name": "run_plug_charge",
        "description": "执行一次即插即充完整流程",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "description": "环境 (pre/test)", "default": "pre"},
                "pile": {"type": "string", "description": "桩编号"},
                "vin": {"type": "string", "description": "车辆VIN码"},
            },
            "required": ["pile", "vin"]
        }
    },
    {
        "name": "run_scan_charge",
        "description": "执行一次扫码充电完整流程",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string", "description": "桩编号"},
                "vin": {"type": "string", "description": "车辆VIN码"},
                "uid": {"type": "string", "description": "用户UID"},
            },
            "required": ["pile", "vin", "uid"]
        }
    },
    {
        "name": "run_scenario_summary",
        "description": "执行充电小结场景",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string"}, "vin": {"type": "string"}, "uid": {"type": "string"},
            },
            "required": ["pile", "vin", "uid"]
        }
    },
    {
        "name": "run_scenario_satisfaction",
        "description": "执行充电需求功率满足度场景 (normal/mismatch/shunt)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string"}, "vin": {"type": "string"},
                "mode": {"type": "string", "default": "normal"},
            },
            "required": ["pile", "vin"]
        }
    },
    {
        "name": "run_scenario_identity_theft",
        "description": "执行身份盗用监控场景 (normal/bat-type/ah-bias/kwh-bias)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string"}, "vin": {"type": "string"},
                "mode": {"type": "string", "default": "normal"},
                "vsrc": {"type": "integer", "default": 0},
            },
            "required": ["pile", "vin"]
        }
    },
    {
        "name": "fault_error",
        "description": "模拟充电桩故障",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string"},
                "code": {"type": "string", "default": "E07"},
            },
            "required": ["pile"]
        }
    },
    {
        "name": "fault_estop",
        "description": "模拟充电桩急停 (E05)",
        "inputSchema": {
            "type": "object",
            "properties": {"env": {"type": "string", "default": "pre"}, "pile": {"type": "string"}},
            "required": ["pile"]
        }
    },
    {
        "name": "fault_upgrading",
        "description": "模拟充电桩升级中 (status=6)",
        "inputSchema": {
            "type": "object",
            "properties": {"env": {"type": "string", "default": "pre"}, "pile": {"type": "string"}},
            "required": ["pile"]
        }
    },
    {
        "name": "fault_start_fail",
        "description": "模拟充电启动失败 (state=255)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string"},
                "reason": {"type": "integer", "default": 1},
            },
            "required": ["pile"]
        }
    },
    {
        "name": "fault_gun_lock",
        "description": "模拟锁枪异常 (E71)",
        "inputSchema": {
            "type": "object",
            "properties": {"env": {"type": "string", "default": "pre"}, "pile": {"type": "string"}},
            "required": ["pile"]
        }
    },
    {
        "name": "send_raw_msg",
        "description": "发送自定义JSON报文到MQTT",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "default": "pre"},
                "pile": {"type": "string"},
                "msg_json": {"type": "string", "description": "完整JSON报文"},
            },
            "required": ["pile", "msg_json"]
        }
    },
]


# ─── Tool 执行 ───

def execute_tool(name, args):
    env = args.get("env", "pre")
    pile = args.get("pile", ENV_CONFIG[env]["pile"])
    cfg = ENV_CONFIG[env]
    vin = args.get("vin", cfg["vin"])
    uid = args.get("uid", cfg["uid"])
    cif = 1

    c = Charger(pile, speed=2.0, env=env)
    try:
        if name == "run_plug_charge":
            (tid, oid), log = capture_output(c.plug_charge, vin, cif, 90, 20, 90, 3)
            return f"即插即充完成 ✓\ntradeID: {tid}\norderID: {oid or '(空)'}"

        elif name == "run_scan_charge":
            (tid, oid), log = capture_output(c.scan_charge, vin, cif, uid, 90, 20, 90, 3)
            return f"扫码充电完成 ✓\ntradeID: {tid}\norderID: {oid or '(空)'}"

        elif name == "run_scenario_summary":
            (tid, oid), log = capture_output(c.scenario_summary, vin, cif, uid, 90, 20, 90, 3, 114)
            return f"充电小结完成 ✓\ntradeID: {tid}\norderID: {oid or '(空)'}"

        elif name == "run_scenario_satisfaction":
            mode = args.get("mode", "normal")
            (tid, oid), log = capture_output(c.scenario_satisfaction, vin, cif, 90, 20, 90, 3, mode, 4)
            return f"满足度场景完成 ✓ (模式: {mode})\ntradeID: {tid}"

        elif name == "run_scenario_identity_theft":
            mode = args.get("mode", "normal")
            vsrc = args.get("vsrc", 0)
            (tid, oid), log = capture_output(c.scenario_identity_theft, vin, cif, vsrc=vsrc, mode=mode)
            return f"身份盗用场景完成 ✓ (模式: {mode})\ntradeID: {tid}"

        elif name == "fault_error":
            code = args.get("code", "E07")
            capture_output(c.fault_error, cif, code)
            return f"故障模拟完成 ✓ (errcode={code})"

        elif name == "fault_estop":
            capture_output(c.fault_estop, cif)
            return "急停模拟完成 ✓ (errcode=E05)"

        elif name == "fault_upgrading":
            capture_output(c.fault_upgrading, cif)
            return "升级中模拟完成 ✓ (status=6)"

        elif name == "fault_start_fail":
            reason = args.get("reason", 1)
            capture_output(c.fault_start_fail, cif, vin, reason)
            return f"启动失败模拟完成 ✓ (reason={reason})"

        elif name == "fault_gun_lock":
            capture_output(c.fault_gun_lock, cif)
            return "锁枪模拟完成 ✓ (errcode=E71)"

        elif name == "send_raw_msg":
            msg_json = args.get("msg_json", "{}")
            json.loads(msg_json)
            c.pub(msg_json, "MCP-发送")
            return f"报文已发送 ✓\n{msg_json}"

        else:
            return f"未知工具: {name}"
    finally:
        try:
            c.client.disconnect()
            c.client.loop_stop()
        except:
            pass


# ─── MCP stdio 主循环 ───

def main():
    """标准 stdio JSON-RPC MCP Server"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
        except (json.JSONDecodeError, Exception):
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        response = None

        if method == "initialize":
            response = {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mqtt-charger", "version": "1.0.0"}
                }
            }

        elif method == "notifications/initialized":
            continue  # 无需响应

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": TOOLS}
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                result_text = execute_tool(tool_name, tool_args)
                response = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}]
                    }
                }
            except Exception as e:
                response = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"执行失败: {str(e)}"}],
                        "isError": True
                    }
                }

        elif method == "shutdown":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            break

        else:
            if msg_id:
                response = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

        if response:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
