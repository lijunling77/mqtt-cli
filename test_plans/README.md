# 📋 批量场景编排

将多个充电桩模拟操作编排成一个 YAML 文件，一次性按顺序执行。

## 使用方法

### 方式一：命令行
```bash
python run_plan.py test_plans/daily_smoke.yaml
python run_plan.py test_plans/full_regression.yaml --env test
```

### 方式二：Kiro 自然语言
在 Kiro 聊天中说：
- "按 daily_smoke.yaml 跑一遍"
- "执行 full_regression 测试计划"

### 方式三：飞书机器人
@机器人 执行测试计划 daily_smoke

## 编排文件格式

```yaml
name: 测试计划名称
description: 描述
env: pre                    # 默认环境（可选，默认 pre）
pile: XPAC2017YS03240002   # 默认桩编号（可选，用配置文件默认值）
vin: TEST2K0Y5JI4P6BC7     # 默认 VIN（可选）
uid: "8102985"              # 默认 UID（可选）

steps:
  - action: plug_charge     # 操作类型
    name: 即插即充测试       # 步骤名称（可选）

  - action: scan_charge
    name: 扫码充电测试
    uid: "8102985"          # 覆盖默认 UID

  - action: fault_error
    code: E07               # 操作特有参数

  - action: sleep
    seconds: 5              # 等待 5 秒
```

## 支持的 action

| action | 说明 | 额外参数 |
|--------|------|---------|
| plug_charge | 即插即充 | pile, vin |
| scan_charge | 扫码充电 | pile, vin, uid |
| summary | 充电小结 | pile, vin, uid |
| satisfaction | 满足度场景 | mode (normal/mismatch/shunt) |
| identity_theft | 身份盗用 | mode (normal/bat-type/ah-bias/kwh-bias) |
| fault_error | 故障模拟 | code (默认 E07) |
| fault_estop | 急停模拟 | — |
| fault_upgrading | 升级中模拟 | — |
| fault_start_fail | 启动失败 | reason |
| fault_gun_lock | 锁枪模拟 | — |
| sleep | 等待 | seconds |

每个 step 可以单独指定 env、pile、vin、uid 覆盖全局默认值。
