# MQTT 充电桩模拟工具 — Kiro 使用说明

## 前置准备

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 用 Kiro 打开项目
用 Kiro 打开本项目文件夹，Skill 会自动加载。

---

## 三种使用方式

### 方式一：Kiro 自然语言（推荐）

在 Kiro 聊天中直接用中文描述你要做的事，Kiro 会自动执行对应命令。

示例：
- "用 pre 环境桩 XPAC2017YS03240002 跑一次即插即充"
- "扫码充电，桩编码 XPAC2017YS03240002，UID 8102985"
- "批量跑 5 次即插即充"
- "跑一次充电小结"
- "模拟满足度场景，车桩错配模式"
- "模拟身份盗用，电池类型不一致"
- "模拟桩故障 E07"
- "模拟急停"
- "发送一条 yx 报文，status=6"

如果需要引用 Skill 获取更多命令提示，在聊天中输入 `#mqtt-charger`。

### 方式二：交互式菜单

直接运行，进入交互式菜单：
```bash
python mqtt_cli.py
```

看到菜单后按数字选择：
```
主菜单
[1] 单次跑充电订单
[2] 批量跑充电订单
[3] 场景脚本
[4] 异常状态模拟
[5] 单条报文发送
[6] 预发充值钱包
[7] 关闭订单
[s] 设置（切换环境）
[q] 退出
```

快捷操作：
- 输入 `q` → 返回主菜单
- 输入 `qq` → 直接退出程序
- 直接回车 → 使用默认值

### 方式三：命令行直接调用

适合脚本调用或 CI/CD：

```bash
# 即插即充
python mqtt_cli.py run plug --pile XPAC2017YS03240002 --vin TEST2K0Y5JI4P6BC7

# 扫码充电
python mqtt_cli.py run scan --pile XPAC2017YS03240002 --uid 8102985

# 批量跑 10 次
python mqtt_cli.py run plug --loop 10

# 充电小结
python mqtt_cli.py scenario summary --pile XPAC2017YS03240002 --uid 8102985

# 满足度（支持多模式逗号分隔）
python mqtt_cli.py scenario satisfaction --mode normal,mismatch,shunt

# 身份盗用
python mqtt_cli.py scenario identity-theft --mode bat-type

# 故障模拟
python mqtt_cli.py fault error --code E07

# 急停
python mqtt_cli.py fault estop

# 升级中
python mqtt_cli.py fault upgrading

# 发送自定义 JSON
python mqtt_cli.py send --json '{"msg":"yx","cif":1,"status":0}'

# 使用 test 环境
python mqtt_cli.py --env test run plug
```

---

## 功能详解

### 单次/批量跑充电订单
- 输入：桩编码、VIN、UID（扫码时）
- 其他参数（SOC、电池类型等）使用配置文件默认值
- 完成后打印 tradeID 和 orderID

### 充电小结
- 走扫码充电流程 + 多条不同功率 BMS 数据
- 输入：桩编码、VIN、UID

### 电池充检
1. 输入桩编码、VIN、UID
2. 自动跑充电到进行中（SOC<25）
3. 提示在 APP 执行充检
4. 按回车后自动获取充检 ID
5. 选择充检结果
6. 发送充检报文
7. 确认后结束充电

### 充电需求功率满足度
- 三种模式：需求低预期高 / 车桩错配 / 同车分流
- 发完 BMS 后可选择继续发其他模式或结束充电

### 身份盗用
- 四种模式：正常 / 电池类型不一致 / 额定容量偏差 / 标定能量偏差
- 走即插即充流程，不需要 UID

### 异常状态模拟
- 故障（E07）/ 急停（E05）/ 升级中（status=6）
- 默认 5 秒发一次，发 3 次
- 发完可选择继续发或结束

### 预发充值钱包
- 输入用户 UID 和金额（默认 9 万元）

### 关闭订单
- 输入订单号，自动根据环境选择域名

---

## 配置文件

`config.yaml` 和程序放在同一目录，可修改默认参数：

```yaml
environments:
  pre:
    pile: "XPAC2017YS03240002"    # 默认桩编码
    vin: "TEST2K0Y5JI4P6BC7"      # 默认 VIN
    uid: "8102985"                  # 默认 UID
  test:
    pile: "559847003"
    vin: "TESTNUYCXPKWVTIZF"
    uid: "1160057"

defaults:
  env: "pre"       # 默认环境
  speed: 2.0       # 速度倍数
```

---

## 给不用 Kiro 的人

### 方案一：用其他 AI 工具（Cursor / Claude Desktop / VS Code Copilot）

本项目的 MCP Server 支持所有兼容 MCP 协议的 AI 工具。详见 `mcp-config/README.md`。

简单来说：
1. 克隆项目，安装依赖
2. 在对应工具中配置 MCP（指向 `mqtt_mcp_server.py`）
3. 在 AI 聊天中用自然语言操作

### 方案二：飞书机器人

在飞书群里 @机器人 即可操作，不需要任何开发工具。详见 `feishu_bot.py` 顶部说明。

### 方案三：exe 交互式菜单

发这三个文件：
1. `dist/mqtt_cli.exe` — 主程序
2. `config.yaml` — 配置文件
3. `使用说明.md` — 使用文档

放在同一目录，双击 exe 即可使用。
