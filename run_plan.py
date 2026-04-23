# -*- coding: utf-8 -*-
"""
批量场景编排运行器
读取 YAML 测试计划文件，按顺序执行每个步骤。

用法：
  python run_plan.py test_plans/daily_smoke.yaml
  python run_plan.py test_plans/full_regression.yaml --env test
  python run_plan.py test_plans/daily_smoke.yaml --pile XPAC2017YS03240002
"""
import argparse
import io
import os
import sys
import time
import logging
import yaml
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime

os.environ["MQTT_CLI_MCP_MODE"] = "1"

from mqtt_cli import ENV_CONFIG, Charger

logging.basicConfig(level=logging.INFO, format='%(asctime)s [编排] %(message)s')
logger = logging.getLogger(__name__)


def capture_output(func, *args, **kwargs):
    """捕获函数的 print 输出"""
    buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err_buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


def execute_step(charger, step, defaults):
    """执行单个步骤，返回 (success, result_text)"""
    action = step["action"]
    env = step.get("env", defaults["env"])
    cfg = ENV_CONFIG.get(env, ENV_CONFIG["pre"])
    pile = step.get("pile", defaults.get("pile", cfg["pile"]))
    vin = step.get("vin", defaults.get("vin", cfg["vin"]))
    uid = step.get("uid", defaults.get("uid", cfg["uid"]))
    cif = 1

    # 如果桩编号变了，需要重建 Charger
    if pile != charger.pile:
        charger.client.disconnect()
        charger.client.loop_stop()
        charger = Charger(pile, speed=2.0, env=env)

    c = charger

    if action == "sleep":
        seconds = step.get("seconds", 3)
        time.sleep(seconds)
        return True, f"等待 {seconds} 秒", c

    elif action == "plug_charge":
        (tid, oid), _ = capture_output(c.plug_charge, vin, cif, 90, 20, 90, 3)
        return True, f"tradeID: {tid} | orderID: {oid or '(空)'}", c

    elif action == "scan_charge":
        (tid, oid), _ = capture_output(c.scan_charge, vin, cif, uid, 90, 20, 90, 3)
        return True, f"tradeID: {tid} | orderID: {oid or '(空)'}", c

    elif action == "summary":
        (tid, oid), _ = capture_output(c.scenario_summary, vin, cif, uid, 90, 20, 90, 3, 114)
        return True, f"tradeID: {tid} | orderID: {oid or '(空)'}", c

    elif action == "satisfaction":
        mode = step.get("mode", "normal")
        (tid, oid), _ = capture_output(c.scenario_satisfaction_start, vin, cif, 90, 20, 90, 3, mode, 4)
        capture_output(c.scenario_satisfaction_finish, tid, vin, cif, 20, 90)
        return True, f"模式: {mode} | tradeID: {tid}", c

    elif action == "identity_theft":
        mode = step.get("mode", "normal")
        vsrc = step.get("vsrc", 0)
        (tid, oid), _ = capture_output(c.scenario_identity_theft, vin, cif, vsrc=vsrc, mode=mode)
        return True, f"模式: {mode} | tradeID: {tid}", c

    elif action == "fault_error":
        code = step.get("code", "E07")
        capture_output(c.fault_error, cif, code)
        return True, f"errcode={code}", c

    elif action == "fault_estop":
        capture_output(c.fault_estop, cif)
        return True, "errcode=E05", c

    elif action == "fault_upgrading":
        capture_output(c.fault_upgrading, cif)
        return True, "status=6", c

    elif action == "fault_start_fail":
        reason = step.get("reason", 1)
        capture_output(c.fault_start_fail, cif, vin, reason)
        return True, f"reason={reason}", c

    elif action == "fault_gun_lock":
        capture_output(c.fault_gun_lock, cif)
        return True, "errcode=E71", c

    else:
        return False, f"未知 action: {action}", c


def run_plan(plan_path, env_override=None, pile_override=None):
    """执行测试计划"""
    with open(plan_path, 'r', encoding='utf-8') as f:
        plan = yaml.safe_load(f)

    plan_name = plan.get("name", os.path.basename(plan_path))
    description = plan.get("description", "")
    steps = plan.get("steps", [])

    # 全局默认值
    defaults = {
        "env": env_override or plan.get("env", "pre"),
        "pile": pile_override or plan.get("pile"),
        "vin": plan.get("vin"),
        "uid": plan.get("uid"),
    }
    # 清理 None 值
    defaults = {k: v for k, v in defaults.items() if v is not None}

    env = defaults.get("env", "pre")
    cfg = ENV_CONFIG.get(env, ENV_CONFIG["pre"])
    pile = defaults.get("pile", cfg["pile"])

    print(f"\n{'='*60}")
    print(f"📋 {plan_name}")
    if description:
        print(f"   {description}")
    print(f"   环境: {env} | 桩: {pile} | 步骤数: {len(steps)}")
    print(f"{'='*60}")

    start_time = time.time()
    success_count = 0
    fail_count = 0
    skip_count = 0
    results = []

    # 创建 Charger（整个计划复用）
    charger = Charger(pile, speed=2.0, env=env)

    try:
        for i, step in enumerate(steps, 1):
            action = step.get("action", "unknown")
            name = step.get("name", action)

            if action == "sleep":
                seconds = step.get("seconds", 3)
                print(f"\n  ⏳ [{i}/{len(steps)}] 等待 {seconds} 秒...")
                time.sleep(seconds)
                results.append({"step": i, "name": name, "status": "skip", "detail": f"{seconds}s"})
                skip_count += 1
                continue

            print(f"\n  ▶ [{i}/{len(steps)}] {name}...", end=" ", flush=True)

            try:
                ok, detail, charger = execute_step(charger, step, defaults)
                if ok:
                    print(f"✅ {detail}")
                    results.append({"step": i, "name": name, "status": "pass", "detail": detail})
                    success_count += 1
                else:
                    print(f"❌ {detail}")
                    results.append({"step": i, "name": name, "status": "fail", "detail": detail})
                    fail_count += 1
            except Exception as e:
                print(f"❌ {str(e)}")
                results.append({"step": i, "name": name, "status": "fail", "detail": str(e)})
                fail_count += 1

    finally:
        try:
            charger.client.disconnect()
            charger.client.loop_stop()
        except:
            pass

    elapsed = time.time() - start_time

    # 汇总报告
    print(f"\n{'='*60}")
    print(f"📊 执行报告 — {plan_name}")
    print(f"{'─'*60}")
    print(f"  总步骤: {len(steps)}  |  ✅ 成功: {success_count}  |  ❌ 失败: {fail_count}  |  ⏳ 跳过: {skip_count}")
    print(f"  耗时: {elapsed:.1f} 秒")
    print(f"{'─'*60}")

    for r in results:
        if r["status"] == "skip":
            continue
        icon = "✅" if r["status"] == "pass" else "❌"
        print(f"  {icon} [{r['step']}] {r['name']}: {r['detail']}")

    print(f"{'='*60}")

    if fail_count > 0:
        print(f"\n  ⚠️  有 {fail_count} 个步骤失败，请检查！")
        return False
    else:
        print(f"\n  🎉 全部通过！")
        return True


def main():
    parser = argparse.ArgumentParser(description="批量场景编排运行器")
    parser.add_argument("plan", help="测试计划 YAML 文件路径")
    parser.add_argument("--env", help="覆盖环境 (pre/test)", default=None)
    parser.add_argument("--pile", help="覆盖桩编号", default=None)
    args = parser.parse_args()

    if not os.path.exists(args.plan):
        print(f"❌ 文件不存在: {args.plan}")
        sys.exit(1)

    success = run_plan(args.plan, args.env, args.pile)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
