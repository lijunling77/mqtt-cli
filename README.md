# ⚡ MQTT 充电桩模拟 CLI 工具

模拟充电桩向运营平台发送 MQTT 报文的命令行工具，支持充电流程模拟、场景脚本、异常状态模拟等功能。

## 环境准备

**Python 版本**: 3.8+

```bash
pip install -r requirements.txt
```

## 快速开始

### 第 1 步：配置环境
编辑 `config.yaml`，确认 MQTT 地址和桩编号等参数。默认使用 pre 环境，开箱即用。

### 第 2 步：启动工具
```bash
python mqtt_cli.py
```

### 第 3 步：选择模式
启动后会显示交互式菜单，按数字选择即可：

```
⚡ MQTT 充电桩模拟 CLI v1.0.0
  环境: pre | 桩: XPAC2017YS03240002 | 速度: 2.0x

──────────────────────────────────────────────────
  主菜单
  [1] 单次跑充电订单 — 执行一次完整充电流程
  [2] 批量跑充电订单 — 循环执行多次充电流程
  [3] 场景脚本       — 充电小结/电池充检/满足度/身份盗用
  [4] 异常状态模拟   — 故障/急停/升级中/启动失败/锁枪/离线
  [5] 单条报文发送   — 单独发送某类型 MQTT 报文（12 种）
  [6] 预发充值钱包   — 给指定用户充值钱包余额
  [7] 关闭订单       — 输入订单号关闭订单
  [s] 设置           — 切换环境
  [q] 退出
```

## 菜单结构

| 主菜单 | 子菜单 | 说明 |
|--------|--------|------|
| 1. 单次跑充电订单 | 即插即充 / 扫码充电 | 执行一次完整充电流程，完成后打印 tradeID 和 orderID |
| 2. 批量跑充电订单 | 即插即充 / 扫码充电 | 循环执行多次，每轮打印 tradeID |
| 3. 场景脚本 | 充电小结 | 完整充电 + 多条不同功率 BMS 数据 |
| | 电池充检 | 需先跑充电订单获取 tradeID |
| | 充电需求功率满足度 | 模拟 normal/mismatch/shunt 三种场景 |
| | 身份盗用 | 模拟电池类型不一致/容量偏差等 |
| 4. 异常状态模拟 | 故障 | 发送故障遥信 (errcode=E07) |
| | 急停 | 发送急停遥信 (errcode=E05) |
| | 升级中 | 发送升级中遥信 (status=6) |
| | 启动失败 | 发送 starting(state=255)（命令行模式） |
| | 锁枪 | 发送锁枪遥信 (errcode=E71)（命令行模式） |
| | 离线 | 断开连接 → 等待 → 重连 → 离线交易（命令行模式） |
| 5. 单条报文发送 | yx/ycBMS/starting 等 | 单独发送某类型报文（12 种） |
| 6. 预发充值钱包 | — | 给指定用户充值钱包余额 |
| 7. 关闭订单 | — | 输入订单号关闭订单 |

## 非交互模式

也可以通过命令行参数直接执行，不进入菜单：

```bash
# 即插即充
python mqtt_cli.py --scan=false --vin TEST2K0Y5JI4P6BC7

# 扫码充电
python mqtt_cli.py --scan --uid 8102985

# 批量跑 10 次
python mqtt_cli.py --loop 10

# 使用 test 环境
python mqtt_cli.py --env test --scan
```

## 批量场景编排

将多个操作编排成 YAML 文件，一次性按顺序执行：

```bash
python run_plan.py test_plans/daily_smoke.yaml        # 每日冒烟
python run_plan.py test_plans/full_regression.yaml     # 全量回归
python run_plan.py test_plans/fault_tests.yaml --env test  # 指定环境
```

内置 6 个测试计划，覆盖充电流程、场景脚本、异常模拟、跨环境等。详见 `test_plans/README.md`。

## AI 工具集成

### Kiro / Cursor / Claude Desktop / VS Code Copilot / 灵犀

本项目已为各 AI 工具准备好规则文件，克隆项目后自动生效：

| AI 工具 | 规则文件 |
|---------|---------|
| Kiro | `.kiro/skills/mqtt-charger/SKILL.md` + MCP |
| Cursor | `.cursorrules` + MCP |
| VS Code Copilot | `.github/copilot-instructions.md` + MCP |
| Claude Desktop | MCP 配置 |
| 灵犀 | `mcp-config/lingxi/rules.md` |

MCP 协议配置详见 `mcp-config/README.md`。

## 配置文件说明

`config.yaml` 包含三个部分：

- **environments**: 多环境配置（MQTT 地址、HTTP 接口、默认桩编号/VIN/UID）
- **defaults**: 通用默认参数（SOC、电池类型等）
- **battery**: 电池/BMS 参数（starting 报文用）

参数优先级：命令行参数 > 交互式输入 > 配置文件 > 内置默认值

## 常见问题

**Q: MQTT 连接失败怎么办？**
A: 检查 config.yaml 中的 mqtt_ip 和 mqtt_port 是否正确，确认网络能访问该地址。

**Q: tradeID 在哪里找？**
A: 每次充电流程完成后会醒目打印 `📋 tradeID: xxx | orderID: xxx`。电池充检场景需要用到这个 tradeID。

**Q: 如何切换环境？**
A: 启动时加 `--env test` 参数，或在 config.yaml 中修改 `defaults.env`。

**Q: 扫码充电创建订单失败？**
A: 检查 uid 是否正确，以及 url_equip/url_order 接口是否可访问。工具会记录错误日志并继续执行。

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller --onefile mqtt_cli.py
```

打包后的 `mqtt_cli.exe` 在 `dist/` 目录下，将 exe 和 `config.yaml` 放在同一目录即可使用。


---
*Last updated: 2026-04-23*
