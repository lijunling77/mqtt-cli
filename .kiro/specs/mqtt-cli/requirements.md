# 需求文档

## 简介

本项目旨在重构和扩展现有的 MQTT 充电桩模拟 CLI 工具，使其支持四大类脚本运行模式：单次跑充电订单、批量跑充电订单、场景脚本（充电小结、电池充检、满足度、身份盗用）和异常状态模拟。CLI 启动后通过交互式菜单引导用户选择运行模式，基于现有的 MQTT 连接层（`mqtt_connect.py`）和直流桩消息模板（`mqtt_msg_dc.py`），支持 pre 和 test 两套环境配置。

## 术语表

- **CLI**: 命令行界面工具，用户通过终端命令与系统交互的入口
- **充电桩模拟器**: 本系统的核心组件，模拟真实充电桩向平台发送 MQTT 消息
- **MQTT_Client**: 基于 paho-mqtt 的 MQTT 连接客户端，封装在 `mqtt_connect.py` 的 Subscription 类中
- **消息模板**: 封装在 `mqtt_msg_dc.py` 的 MqttMsgDC 类中，提供各类 MQTT 消息的 JSON 构造方法
- **即插即充**: 车辆插枪后自动识别并启动充电的模式，无需用户扫码操作
- **扫码充电**: 用户通过 APP 扫描充电枪二维码后启动充电的模式，需要调用 HTTP 接口获取二维码和创建订单
- **遥信（yx）**: 充电桩状态信号上报，包含桩状态（空闲/工作/完成）、告警、故障码等
- **遥测采集（ycAnalog）**: 充电桩电气参数采集数据，包含电压、电流、功率等
- **遥测计量（ycMeas）**: 充电计量数据，包含各时段电量
- **遥测BMS（ycBMS）**: 电池管理系统数据，包含电压、电流、SOC、温度等
- **bootNoti**: 充电桩启动通知消息，上报桩的软硬件版本信息
- **starting**: 充电启动状态消息，state 字段从 0 到 5 表示启动各阶段
- **chargEnd**: 充电结束消息，上报充电结束原因和汇总数据
- **trade**: 充电交易上传消息，上报完整的交易计费数据
- **olTrade**: 离线交易上传消息，桩离线期间产生的交易数据补传
- **carChk**: 车辆验证请求消息，用于即插即充场景的车辆身份识别
- **cdProgress**: 电池充检进度/状态消息，协议 v1.19 新增
- **cdReq**: 电池充检请求消息，协议 v1.19 新增
- **充电小结**: 充电结束后的数据汇总上报场景，包含 chargEnd 和 trade 消息的完整流程
- **电池充检**: 协议 v1.19 新增功能，通过 cdProgress/cdReq 消息模拟电池检测流程
- **满足度**: 充电需求功率满足度，通过 ycBMS 报文中的输出功率与需求功率比值来衡量充电功率是否满足车辆需求
- **身份盗用**: 车辆验证/鉴权异常场景，模拟 VIN 不匹配或鉴权失败等情况
- **Topic**: MQTT 消息主题，格式为 `/${productKey}/${deviceName}/update`（上报）和 `/${productKey}/${deviceName}/get`（获取）
- **SOC**: State of Charge，电池荷电状态百分比
- **CIF**: Charging Interface，充电接口编号
- **VIN**: Vehicle Identification Number，车辆识别码

## 需求

### 需求 1：CLI 交互式菜单架构

**用户故事：** 作为测试工程师，我希望 CLI 工具启动后展示交互式菜单，让我选择运行模式，以便快速进入所需的测试场景。

#### 验收标准

1. WHEN 用户启动 CLI 时，THE CLI SHALL 显示主菜单，包含以下五个选项：
   - `[1] 单次跑充电订单` — 执行一次完整的充电流程（即插即充或扫码充电）
   - `[2] 批量跑充电订单` — 循环执行多次充电流程
   - `[3] 场景脚本` — 进入场景子菜单（充电小结、电池充检、满足度、身份盗用）
   - `[4] 异常状态模拟` — 进入异常模拟子菜单（故障、急停、升级中、启动失败、锁枪、离线）
   - `[5] 单条报文发送` — 单独发送某一类型的 MQTT 报文
2. WHEN 用户选择 `[3] 场景脚本` 时，THE CLI SHALL 显示场景子菜单：
   - `[1] 充电小结`
   - `[2] 电池充检`
   - `[3] 充电需求功率满足度`
   - `[4] 身份盗用`
3. WHEN 用户选择 `[4] 异常状态模拟` 时，THE CLI SHALL 显示异常子菜单：
   - `[1] 故障` — 发送故障遥信报文
   - `[2] 急停` — 发送急停遥信报文
   - `[3] 升级中` — 发送升级中遥信报文
   - `[4] 启动失败` — 发送启动失败报文
   - `[5] 锁枪` — 发送锁枪遥信报文
   - `[6] 离线` — 模拟桩离线
4. THE CLI SHALL 在选择模式后，交互式提示用户输入该模式所需的参数（如桩编号、VIN、环境等），并提供默认值
5. THE CLI SHALL 支持 `--env` 启动参数，允许用户在启动时预设环境（`pre` 或 `test`），默认为 `pre`
6. THE CLI SHALL 支持 `--pile` 启动参数预设桩编号，默认值为 `XPAC2017YS03240002`
7. THE CLI SHALL 支持 `--cif` 启动参数预设充电接口编号，默认值为 `1`
8. THE CLI SHALL 支持 `--speed` 启动参数预设模拟速度倍数，默认值为 `2.0`
9. THE CLI SHALL 同时支持非交互模式：当用户通过命令行直接传入子命令（如 `python mqtt_cli.py run plug`）时，跳过菜单直接执行


### 需求 2：环境配置管理

**用户故事：** 作为测试工程师，我希望 CLI 工具能管理多套环境配置（pre/test），以便我能在不同环境间快速切换进行测试。

#### 验收标准

1. WHEN 用户指定 `--env pre` 时，THE 充电桩模拟器 SHALL 使用 pre 环境的 MQTT 地址（47.96.240.241:12883）和 HTTP 接口地址
2. WHEN 用户指定 `--env test` 时，THE 充电桩模拟器 SHALL 使用 test 环境的 MQTT 地址和 HTTP 接口地址
3. THE 充电桩模拟器 SHALL 在启动时打印当前使用的环境名称、MQTT 地址和 Topic 信息
4. IF 用户指定了不存在的环境名称，THEN THE CLI SHALL 输出错误提示并列出可用的环境名称

### 需求 3：单次跑充电订单

**用户故事：** 作为测试工程师，我希望通过"单次跑充电订单"模式执行一次完整的充电流程（即插即充或扫码充电），以便快速验证单笔充电订单的处理逻辑。

#### 验收标准

1. WHEN 用户选择"单次跑充电订单"时，THE CLI SHALL 提示用户选择充电模式：`[1] 即插即充` 或 `[2] 扫码充电`
2. WHEN 用户选择即插即充时，THE 充电桩模拟器 SHALL 按以下顺序执行流程：上报空闲（yx）→ 车辆验证（carChk）→ 启动状态（starting state 0-5）→ 充电数据上报（ycBMS/yx/ycMeas）→ 充电结束（chargEnd）→ 交易上传（trade）→ 恢复空闲（yx）
3. WHEN 用户选择扫码充电时，THE 充电桩模拟器 SHALL 按以下顺序执行流程：上报空闲（yx）→ 等待插枪（yx status=5）→ 获取二维码并创建订单（HTTP）→ 启动状态（starting state 1-5）→ 充电数据上报（ycBMS/yx/ycMeas）→ 充电结束（chargEnd）→ 交易上传（trade）→ 恢复空闲（yx）
4. THE 充电桩模拟器 SHALL 支持以下参数（交互式提示或命令行传入）：
   - `--vin`：车辆 VIN 码，默认值为 `TEST2K0Y5JI4P6BC7`
   - `--uid`：用户 UID（扫码充电用），默认值为 `8102985`
   - `--soc`、`--bsoc`、`--esoc`：BMS SOC、开始 SOC、结束 SOC
   - `--bat`：电池类型（3=磷酸铁锂，6=三元锂），默认值为 `3`
5. WHEN 扫码充电中获取二维码或创建订单接口调用失败时，THE 充电桩模拟器 SHALL 记录错误日志并使用空字符串继续执行
6. WHEN 执行每个步骤时，THE 充电桩模拟器 SHALL 在终端打印当前步骤编号、步骤名称和发送的消息摘要
7. WHEN 充电流程执行完成后，THE CLI SHALL 在终端醒目打印本次使用的 `tradeID`（交易流水号）和 `orderID`（订单编号），方便用户复制用于后续场景（如电池充检）

### 需求 4：批量跑充电订单

**用户故事：** 作为测试工程师，我希望通过"批量跑充电订单"模式循环执行多次充电流程，以便进行压力测试或批量造数。

#### 验收标准

1. WHEN 用户选择"批量跑充电订单"时，THE CLI SHALL 依次提示用户：(a) 选择充电模式：`[1] 即插即充` 或 `[2] 扫码充电`；(b) 输入循环次数（默认 `1`）
2. THE 充电桩模拟器 SHALL 支持 `--loop` 参数指定循环执行次数，默认值为 `1`
3. THE 充电桩模拟器 SHALL 在每轮执行之间等待 5 秒（受 `--speed` 倍速影响）
4. WHEN 循环次数大于 1 时，THE CLI SHALL 在每轮开始时打印当前轮次（如 `第 1/10 轮`）
5. THE 充电桩模拟器 SHALL 在全部轮次完成后打印总结信息，包含完成轮次数
6. THE 充电桩模拟器 SHALL 在每轮充电流程完成后打印该轮的 `tradeID` 和 `orderID`
7. THE 充电桩模拟器 SHALL 复用需求 3 中单次充电订单的所有参数和流程逻辑

### 需求 5：场景脚本 - 充电小结

**用户故事：** 作为测试工程师，我希望通过"充电小结"场景模拟一次完整充电流程，并在充电中阶段发送多条 ycBMS 报文（模拟不同功率数据），以便验证平台充电小结卡片的展示逻辑（最大功率、省时数据、速度标签等）。

> 参考文档：[充电小结1.1总结](https://xiaopeng.feishu.cn/docx/CAqcdpCBKoCOMZx9pEqc6M2pn6b)
>
> 充电小结卡片显示条件：
> - 订单状态为待支付或交易完成
> - 桩类型为直流充电桩
> - 充电时长、充电度数在配置范围内
> - 开始 SOC < 结束 SOC，且均在 0-100 范围内
> - 最高功率在配置范围内
> - 平均功率 > 0 且 <= 最高功率

#### 验收标准

1. WHEN 用户选择"充电小结"场景时，THE 充电桩模拟器 SHALL 执行完整充电流程，并在充电中阶段发送多条 ycBMS 报文，模拟不同的功率数据（r_vol/r_cur/m_vol/m_cur 变化）
2. THE 充电桩模拟器 SHALL 在充电中阶段发送至少 4 条 ycBMS 报文，每条间隔 20 秒（受 `--speed` 倍速影响），参考报文参数为：
   - 第 1 条：`r_vol=392.3, r_cur=-71.3, m_vol=220.0, m_cur=-300.0`
   - 第 2 条：`r_vol=392.3, r_cur=-271.3, m_vol=220.0, m_cur=-300.0`
   - 第 3 条：`r_vol=392.3, r_cur=-271.3, m_vol=888.89, m_cur=-967.0`（高功率）
   - 第 4 条：`r_vol=392.3, r_cur=-171.3, m_vol=20.0, m_cur=-300.0`
3. THE 充电桩模拟器 SHALL 在 chargEnd 消息中包含完整的充电时长、各时段电量、起止 SOC 和结束原因
4. THE 充电桩模拟器 SHALL 在 trade 消息中包含完整的交易计费数据，包含尖峰平谷各时段电量
5. THE 充电桩模拟器 SHALL 支持 `--reason` 参数指定充电结束原因码（CSR），默认值为 `114`（正常结束）
6. WHEN 充电流程完成后，THE CLI SHALL 打印 `tradeID` 和 `orderID`

### 需求 6：场景脚本 - 电池充检

**用户故事：** 作为测试工程师，我希望通过"电池充检"场景模拟充检流程。充检依赖一个已存在的充电订单，因此我需要先手动跑一次充电订单获取 tradeID，然后在充检场景中输入 tradeID、充检 ID 和 VIN 来执行充检。

> 参考文档：[电池充检流程](https://xiaopeng.feishu.cn/docx/IlcddPbp4oNp3fxg21qcbSX2nRd)
>
> 充检前置条件：
> - 车辆支持充检：ner_cust.t_vin_view 表中 VIN 对应的 bat_type、bat_type_desc、battery_error_status、charge_car_series 字段有值
> - 桩支持充检：pileProp 报文中 cdEn=1
> - BMS 支持充检：ycBMS 报文中 cdFlag=2
> - 需要一个已存在的充电订单（先通过"单次跑充电订单"或"批量跑充电订单"创建）

#### 验收标准

**交互式输入**

1. WHEN 用户选择"电池充检"场景时，THE CLI SHALL 依次提示用户输入：
   - `tradeID`：交易流水号（从之前跑的充电订单中获取，必填）
   - `id`：充检 ID（如 `CJ260325114725494609`，默认自动生成格式为 `CJ{YYMMDDHHmmss}{随机6位数字}`）
   - `vin`：车辆 VIN 码（默认值为 `TEST2K0Y5JI4P6BC7`）

**桩属性上报（pileProp）**

2. THE 充电桩模拟器 SHALL 首先发送 pileProp 消息，其中 `cdEn` 字段为 `1`，表示桩支持充检
3. THE 充电桩模拟器 SHALL 发送的 pileProp 报文格式为：`{"msg":"pileProp", "dev":{"vendor":"XPENG", "ratedPower":360.0, "maxOutVol":1000.0, "minOutVol":200.0, "maxOutCur":800.0, "minOutCur":1.0, "cdEn":1}}`

**BMS 充检标志上报（ycBMS）**

4. THE 充电桩模拟器 SHALL 发送 ycBMS 报文，其中 `cdFlag` 字段为 `2`（BMS 支持充检），`tradeID` 为用户输入的值
5. THE 充电桩模拟器 SHALL 在 ycBMS 报文中包含 `soc1` 字段（协议 v1.19 新增）

**充检进度上报（cdProgress）**

6. THE 充电桩模拟器 SHALL 发送 cdProgress 消息模拟充检过程，state 依次为 `1`（待检测）→ `2`/`3`/`4`（检测中）→ `100`（检测完成或取消）
7. THE 充电桩模拟器 SHALL 在 cdProgress 消息中使用用户输入的 `id`（充检 ID）和 `tradeID`
8. WHEN 充检完成（state=100 且 errcode=0）时，THE 充电桩模拟器 SHALL 在 cdProgress 消息中包含 `tradeID`、`vin`、`beginTime`、`endTime`、`bp_r_cur`、`beginSoC`、`endSoC`、`errcode`（0）、`errmsg`（"成功"）字段

**充检结果控制**

9. THE CLI SHALL 提示用户选择充检结果，可选值为：
   - `[1] 检测完成`（state=100, errcode=0），默认值
   - `[2] 平台终止`（state=100, errcode=1）
   - `[3] BMS 禁止充检`（state=100, errcode=2）
   - `[4] BEX1 超时`（state=100, errcode=3）
   - `[5] 暂停充电超时`（state=100, errcode=4）
   - `[6] 脉冲输出超时`（state=100, errcode=5）
   - `[7] 脉冲电流停止超时`（state=100, errcode=6）
   - `[8] 充检时结束充电`（state=100, errcode=7）
   - `[9] 其他错误`（state=100, errcode=99）

**参数控制**

10. THE 充电桩模拟器 SHALL 支持 `--interval` 参数指定充检进度上报间隔（秒），默认值为 `5`

### 需求 7：场景脚本 - 充电需求功率满足度

**用户故事：** 作为测试工程师，我希望通过 `scenario satisfaction` 命令模拟充电需求功率满足度场景，以便验证平台对不同满足度情况（需求低预期高、车桩错配、同车分流/桩故障）的展示和处理逻辑。

> 参考文档：[充电需求功率满足度测试](https://xiaopeng.feishu.cn/docx/Fj6hdItOMo0iEuxXVtXcdlaPn3g)
>
> 满足度计算公式：需求功率满足度 = 输出功率(m_vol × m_cur) / 需求功率(m_vol × r_cur)
> 满足度阈值：95%（低于此值触发提示）

#### 验收标准

**通用流程**

1. WHEN 用户执行 `scenario satisfaction` 命令时，THE 充电桩模拟器 SHALL 执行完整充电流程，并在充电中阶段周期性发送 ycBMS 报文，通过调整 r_vol/r_cur/m_vol/m_cur 参数模拟不同满足度场景
2. THE 充电桩模拟器 SHALL 支持 `--mode` 参数选择满足度场景类型，可选值为 `normal`（需求低预期高）、`mismatch`（车桩错配）、`shunt`（同车分流/桩故障），默认值为 `normal`
3. THE 充电桩模拟器 SHALL 在充电中阶段发送多条 ycBMS 报文，每条间隔 20 秒（受 `--speed` 倍速影响）

**需求低预期高场景 (`--mode normal`)**

4. WHEN 用户指定 `--mode normal` 时，THE 充电桩模拟器 SHALL 发送 ycBMS 报文，其中满足度 >= 95%，即输出功率接近或超过需求功率
5. THE 充电桩模拟器 SHALL 使用的参考报文参数为：`r_vol=392.3, r_cur=-512.3, m_vol=223.0, m_cur=-503.0`

**车桩错配场景 (`--mode mismatch`)**

6. WHEN 用户指定 `--mode mismatch` 时，THE 充电桩模拟器 SHALL 发送 ycBMS 报文，其中 m_cur 大于枪绑定型号的额定电流，模拟车桩功率不匹配
7. THE 充电桩模拟器 SHALL 使用的参考报文参数为：`r_vol=500.1, r_cur=-309.8, m_vol=223.0, m_cur=-294.1`

**同车分流/桩故障场景 (`--mode shunt`)**

8. WHEN 用户指定 `--mode shunt` 时，THE 充电桩模拟器 SHALL 发送 ycBMS 报文，其中输出功率明显低于需求功率，满足度远低于 95%
9. THE 充电桩模拟器 SHALL 使用的参考报文参数为：`r_vol=400.3, r_cur=-212.3, m_vol=223.0, m_cur=-103.0`

**自定义参数**

10. THE 充电桩模拟器 SHALL 支持 `--r-vol`、`--r-cur`、`--m-vol`、`--m-cur` 参数，允许用户自定义 ycBMS 报文中的需求电压、需求电流、输出电压、输出电流值，覆盖预设场景的默认值
11. THE 充电桩模拟器 SHALL 支持 `--bms-count` 参数指定充电中阶段发送 ycBMS 报文的次数，默认值为 `4`

### 需求 8：场景脚本 - 身份盗用

**用户故事：** 作为测试工程师，我希望通过 `scenario identity-theft` 命令模拟身份盗用监控场景，以便验证平台对车辆身份异常（电池类型不一致、电池容量偏差等）的检测、告警和拦截能力。

> 参考文档：[身份盗用监控1.3测试](https://xiaopeng.feishu.cn/docx/LCmYdSefcoQkIdxlPIBcDJukn5f)
>
> 身份盗用判定逻辑：平台通过 carChk 报文中的 VIN 和 vsrc（车辆来源），以及 starting(state=5) 报文中的 batType（电池类型）、ratedAH（蓄电池额定容量）、ratedKWh（蓄电池标定总能量）进行比对判定。
> - 电池类型不一致 → 加入名单并启用，告警+停用+不允许下单
> - 电池类型一致但 ratedAH 或 ratedKWh 偏差 > ±10 → 加入名单并停用，告警需人工核实
> - 电池类型一致且偏差 <= ±10 → 不处理

#### 验收标准

**通用流程**

1. WHEN 用户执行 `scenario identity-theft` 命令时，THE 充电桩模拟器 SHALL 执行即插即充流程，在 carChk 阶段发送指定 VIN 和 vsrc 的车辆验证报文，在 starting(state=5) 阶段发送指定电池参数的启动报文
2. THE 充电桩模拟器 SHALL 支持 `--vin` 参数指定车辆 VIN 码，默认值为小鹏车 VIN `TESTJLZUPT4N0GHBW`；非小鹏车可使用 `G4R63KMMLEC562893`
3. THE 充电桩模拟器 SHALL 支持 `--vsrc` 参数指定车辆来源（0=小鹏汽车/BVM，1=其他，2=其他），默认值为 `0`

**电池参数控制**

4. THE 充电桩模拟器 SHALL 支持 `--bat` 参数指定电池类型（3=磷酸铁锂，6=三元锂），默认值为 `3`
5. THE 充电桩模拟器 SHALL 支持 `--rated-ah` 参数指定蓄电池额定容量（AH），默认值为 `231.9`（正常值）；设置为偏差值如 `211.9` 可触发容量偏差告警
6. THE 充电桩模拟器 SHALL 支持 `--rated-kwh` 参数指定蓄电池标定总能量（KWh），默认值为 `74`（正常值）；设置为偏差值如 `83.0` 可触发能量偏差告警

**预设场景模式**

7. THE 充电桩模拟器 SHALL 支持 `--mode` 参数选择预设场景，可选值为：
   - `bat-type`：电池类型不一致（修改 batType 为与车辆不匹配的值），预期触发"告警+停用+不允许下单"
   - `ah-bias`：蓄电池额定容量偏差 > ±10（修改 ratedAH），预期触发"告警需人工核实"
   - `kwh-bias`：蓄电池标定总能量偏差 > ±10（修改 ratedKWh），预期触发"告警需人工核实"
   - `normal`：所有参数正常，预期不触发任何告警（默认值）

**carChk 报文控制**

8. WHEN vsrc=0（小鹏汽车来源）且 VIN 为小鹏 VIN 时，THE 充电桩模拟器 SHALL 发送 carChk 报文使鉴权通过，后续进入 starting 阶段进行电池参数比对
9. WHEN vsrc=1 或 vsrc=2 且 VIN 为小鹏 VIN 时，THE 充电桩模拟器 SHALL 发送 carChk 报文使鉴权不通过，模拟非 BVM 来源的小鹏车被拦截

### 需求 9：异常状态模拟

**用户故事：** 作为测试工程师，我希望通过 `fault` 子命令模拟各种充电桩异常状态，以便验证平台对异常情况的监控和告警能力。

> 参考文档：[桩异常页面模拟报文](https://xiaopeng.feishu.cn/docx/NI9kd6ulKoJv0Ex9B0pcwmkSnLh)

#### 验收标准

**故障模拟 (`fault error`)**

1. WHEN 用户执行 `fault error` 命令时，THE 充电桩模拟器 SHALL 发送遥信（yx）消息，其中 `error` 字段为 `1`，`errcode` 字段为用户指定的故障码
2. THE 充电桩模拟器 SHALL 支持 `--code` 参数指定故障码（如 `E07`），默认值为 `E07`
3. THE 充电桩模拟器 SHALL 发送的故障报文格式为：`{"msg":"yx", "cif":1, "status":0, "error":1, "errcode":"E07", ...}`

**急停模拟 (`fault estop`)**

4. WHEN 用户执行 `fault estop` 命令时，THE 充电桩模拟器 SHALL 发送遥信（yx）消息，其中 `error` 字段为 `1`，`errcode` 字段为 `E05`
5. THE 充电桩模拟器 SHALL 发送的急停报文格式为：`{"msg":"yx", "cif":1, "status":0, "error":1, "errcode":"E05", ...}`

**升级中模拟 (`fault upgrading`)**

6. WHEN 用户执行 `fault upgrading` 命令时，THE 充电桩模拟器 SHALL 发送遥信（yx）消息，其中 `status` 字段为 `6`（升级中状态）
7. THE 充电桩模拟器 SHALL 发送的升级报文格式为：`{"msg":"yx", "cif":1, "status":6, "error":0, "errcode":"", ...}`

**启动失败模拟 (`fault start-fail`)**

8. WHEN 用户执行 `fault start-fail` 命令时，THE 充电桩模拟器 SHALL 发送 starting 消息，其中 `state` 字段为 `255`（启动失败），并附带启动失败原因码
9. THE 充电桩模拟器 SHALL 支持 `--reason` 参数指定启动失败原因码，默认值为 `1`
10. THE 充电桩模拟器 SHALL 支持 `--errcode` 参数指定启动失败时的故障编码

**锁枪模拟 (`fault gun-lock`)**

11. WHEN 用户执行 `fault gun-lock` 命令时，THE 充电桩模拟器 SHALL 发送遥信（yx）消息，模拟充电完成/启动失败后枪锁未解锁的状态
12. THE 充电桩模拟器 SHALL 发送的锁枪报文满足触发条件：`status=2 && yx1=1 && yx3=1` 或 `status=5 && yx1=1 && yx3=1`，且 `error=1, errcode="E71"`

**离线模拟 (`fault offline`)**

13. WHEN 用户执行 `fault offline` 命令时，THE 充电桩模拟器 SHALL 模拟桩离线场景，先发送 bootNoti 消息，然后断开 MQTT 连接，等待指定时间后重连并发送离线交易（olTrade）消息
14. THE 充电桩模拟器 SHALL 支持 `--duration` 参数指定离线持续时间（秒），默认值为 `30`

**通用参数**

15. THE 充电桩模拟器 SHALL 在所有 fault 子命令中支持 `--repeat` 参数指定报文重复发送次数，默认值为 `1`
16. THE 充电桩模拟器 SHALL 在所有 fault 子命令中支持 `--interval` 参数指定重复发送间隔（秒），默认值为 `30`（与遥信默认上报周期一致）

### 需求 10：消息模板扩展

**用户故事：** 作为测试工程师，我希望消息模板支持电池充检相关的新消息类型，以便 CLI 工具能模拟 v1.19 协议新增的充检功能。

#### 验收标准

1. THE 消息模板 SHALL 提供 `publish_pileProp` 方法，生成桩属性数据消息，包含 `dev` 对象（含 vendor、ratedPower、maxOutVol、minOutVol、maxOutCur、minOutCur、cdEn 等字段）
2. THE 消息模板 SHALL 提供 `publish_cdProgress` 方法，生成电池充检进度消息，包含 `cif`、`id`（充检 ID）、`type`、`state` 字段；当 state=100 时额外包含 `tradeID`、`vin`、`beginTime`、`endTime`、`bp_r_cur`、`beginSoC`、`endSoC`、`errcode`、`errmsg` 字段
3. THE 消息模板 SHALL 在现有 `publish_ycBMS` 方法中新增 `soc1` 和 `cdFlag` 可选参数，支持协议 v1.19 新增字段
4. THE 消息模板 SHALL 生成的所有消息为 JSON 格式、UTF-8 紧凑型编码
5. THE 消息模板 SHALL 生成的消息中包含正确的时间戳字段，格式为 `YYYYMMDDHHmmss`

### 需求 11：执行过程可观测性

**用户故事：** 作为测试工程师，我希望 CLI 工具在执行过程中提供清晰的进度和状态输出，以便我能实时了解脚本执行情况。

#### 验收标准

1. THE CLI SHALL 在每个步骤执行时打印带颜色的步骤编号和步骤名称
2. THE CLI SHALL 在每条 MQTT 消息发送后打印消息标签和消息内容摘要（截取前 120 字符）
3. THE CLI SHALL 在流程完成后打印成功标识和总结信息
4. IF MQTT 连接失败，THEN THE CLI SHALL 输出包含连接地址和错误原因的错误信息，并以非零退出码退出
5. THE CLI SHALL 在启动时打印当前模式、桩编号、VIN、速度倍数和循环次数等关键参数

### 需求 12：参数配置文件

**用户故事：** 作为测试工程师，我希望 CLI 工具支持从配置文件读取默认参数，以便团队成员不用每次手动输入，修改配置文件即可适配自己的测试环境和桩设备。

#### 验收标准

1. THE CLI SHALL 支持从 `config.yaml` 配置文件读取默认参数
2. THE 配置文件 SHALL 包含以下分组配置项：

**环境配置（支持多环境）**
```yaml
environments:
  pre:
    mqtt_ip: "47.96.240.241"
    mqtt_port: 12883
    mqtt_user: "charge-mqtt"
    mqtt_pwd: "vTZLRlmlDJiR"
    public_pile: "XPeng_10002_Charge"
    url_equip: "https://thor.deploy-test.xiaopeng.com/api/xp-thor-asset/asset/equip/search"
    url_order: "https://xmart.deploy-test.xiaopeng.com/biz/v5/chargeOrder/chargeOrderV2"
  test:
    mqtt_ip: "<test_ip>"
    mqtt_port: 12883
    mqtt_user: "charge-private-mqtt"
    mqtt_pwd: "0LZVRlmlD88Y"
    public_pile: "XPeng_TEST_Charge"
    url_equip: "http://thor.test.xiaopeng.local/api/xp-thor-asset/asset/equip/search"
    url_order: "https://10.0.13.28:8553/biz/v5/chargeOrder/chargeOrderV2"
```

**通用默认参数**
```yaml
defaults:
  env: "pre"
  pile: "XPAC2017YS03240002"
  cif: 1
  speed: 2.0
  vin: "TEST2K0Y5JI4P6BC7"
  uid: "8102985"
  soc: 90
  bsoc: 20
  esoc: 90
  bat: 3                    # 电池类型 3=磷酸铁锂 6=三元锂
  rated_ah: 231.9           # 蓄电池额定容量
  rated_kwh: 74             # 蓄电池标定总能量
```

**电池/BMS 参数（starting 报文用）**
```yaml
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
```

3. THE CLI SHALL 按以下优先级加载参数：命令行参数 > 交互式输入 > 配置文件 > 内置默认值
4. IF 配置文件不存在，THEN THE CLI SHALL 使用内置默认值正常运行，不报错
5. THE CLI SHALL 在首次运行时，如果配置文件不存在，提示用户是否生成默认配置文件模板
6. THE CLI SHALL 支持用户自定义新增环境配置（不限于 pre/test），在配置文件的 `environments` 下新增即可

### 需求 13：单条报文发送模式

**用户故事：** 作为测试工程师，我希望能单独发送某一类型的 MQTT 报文（如 yx、ycBMS、starting、chargEnd 等），以便在调试时灵活控制发送的报文内容，不需要跑完整流程。

#### 验收标准

1. THE CLI SHALL 在主菜单中新增第 5 个选项：`[5] 单条报文发送`
2. WHEN 用户选择"单条报文发送"时，THE CLI SHALL 显示可发送的报文类型子菜单：
   - `[1] yx` — 遥信数据
   - `[2] ycBMS` — BMS 数据
   - `[3] ycMeas` — 计量数据
   - `[4] ycAnalog` — 采集数据
   - `[5] starting` — 启动状态
   - `[6] chargEnd` — 充电结束
   - `[7] trade` — 交易上传
   - `[8] carChk` — 车辆验证
   - `[9] bootNoti` — 启动通知
   - `[10] pileProp` — 桩属性
   - `[11] cdProgress` — 充检进度
3. WHEN 用户选择某个报文类型后，THE CLI SHALL 交互式提示用户输入该报文的关键参数（提供默认值），然后发送该报文
4. THE CLI SHALL 在发送后打印完整的报文 JSON 内容
5. THE CLI SHALL 支持 `--repeat` 参数指定重复发送次数，`--interval` 参数指定发送间隔

### 需求 14：新手引导与使用说明

**用户故事：** 作为不熟悉充电桩协议的测试工程师，我希望 CLI 工具提供足够的引导信息，让我不需要阅读协议文档也能正确使用。

#### 验收标准

1. THE CLI SHALL 在主菜单每个选项旁显示简短的中文说明，解释该选项的用途
2. THE CLI SHALL 在交互式输入每个参数时，显示该参数的含义和示例值（如 `桩编号 (如 XPAC2017YS03240002)`）
3. THE CLI SHALL 在场景脚本子菜单中，每个场景旁显示一句话说明预期效果（如 `电池充检 — 模拟充检流程，需先跑一次充电订单`）
4. THE CLI SHALL 在异常模拟子菜单中，每个异常类型旁显示对应的平台预期表现（如 `故障 — 平台显示桩故障状态`）
5. THE CLI SHALL 提供 `--help` 参数，输出完整的使用说明，包含所有子命令和参数的中文描述
6. THE CLI SHALL 在项目根目录生成 `README.md` 使用文档，包含：
   - 环境准备（Python 版本、依赖安装 `pip install -r requirements.txt`）
   - 快速开始（3 步上手：配置环境 → 选择模式 → 执行）
   - 菜单结构总览
   - 每个模式的使用示例和参数说明
   - 配置文件说明
   - 常见问题 FAQ（如 MQTT 连接失败怎么办、tradeID 在哪里找等）

### 需求 15：依赖管理与一键安装

**用户故事：** 作为新接手的测试工程师，我希望能一键安装所有依赖，不需要自己去找缺了哪个包。

#### 验收标准

1. THE 项目 SHALL 提供 `requirements.txt` 文件，列出所有 Python 依赖包及版本
2. THE `requirements.txt` SHALL 至少包含：`paho-mqtt`、`requests`、`fake-useragent`、`pyyaml`
3. THE `README.md` SHALL 包含安装命令：`pip install -r requirements.txt`

### 需求 16：执行完成后返回主菜单

**用户故事：** 作为测试工程师，我希望执行完一个场景后能直接返回主菜单继续选择下一个操作，不需要重新启动 CLI。

#### 验收标准

1. WHEN 任意模式执行完成后，THE CLI SHALL 提示用户：`按回车返回主菜单，输入 q 退出`
2. WHEN 用户按回车时，THE CLI SHALL 返回主菜单，保持 MQTT 连接不断开
3. WHEN 用户输入 `q` 时，THE CLI SHALL 断开 MQTT 连接并退出程序
4. THE CLI SHALL 在返回主菜单时保留当前的环境配置和桩编号设置，不需要重新输入

### 需求 17：打包为可执行文件

**用户故事：** 作为测试工程师，我希望 CLI 工具能打包成独立的可执行文件（.exe），让团队成员不需要安装 Python 环境，双击或命令行直接运行。

#### 验收标准

1. THE 项目 SHALL 支持使用 PyInstaller 打包为单文件可执行程序（`mqtt_cli.exe`）
2. THE 打包后的可执行文件 SHALL 包含所有依赖，无需额外安装 Python 或第三方库
3. THE 可执行文件 SHALL 在首次运行时，如果同目录下没有 `config.yaml`，自动生成默认配置文件模板
4. THE 项目 SHALL 提供打包脚本或 Makefile 命令（如 `python -m PyInstaller --onefile mqtt_cli.py`），方便开发者重新打包
5. THE `README.md` SHALL 包含打包说明和使用说明：
   - 开发者：如何打包（安装 PyInstaller + 执行打包命令）
   - 使用者：下载 exe + 放入 config.yaml（可选）→ 双击运行

### 需求 18：执行日志持久化

**用户故事：** 作为测试工程师，我希望 CLI 工具自动将执行日志保存到文件，以便我在批量执行后能回溯每轮的 tradeID/orderID 和发送的报文内容。

#### 验收标准

1. THE CLI SHALL 在每次启动时自动创建日志文件，路径为 `logs/{YYYYMMDD_HHmmss}.log`
2. THE 日志文件 SHALL 记录所有终端打印的内容，包括步骤信息、发送的报文 JSON、tradeID/orderID、错误信息
3. THE CLI SHALL 在执行结束后打印日志文件路径，方便用户查找
4. THE CLI SHALL 支持 `--log-dir` 参数自定义日志目录，默认为 `./logs/`

### 需求 19：参数输入校验

**用户故事：** 作为不熟悉协议的测试工程师，我希望 CLI 工具在我输入错误参数时给出提示，避免发送无效报文。

#### 验收标准

1. THE CLI SHALL 校验 VIN 码长度为 17 位，不符合时提示重新输入
2. THE CLI SHALL 校验 SOC 值在 0-100 范围内（bsoc < esoc），不符合时提示重新输入
3. THE CLI SHALL 校验电池类型为有效值（3 或 6），不符合时提示重新输入
4. THE CLI SHALL 校验桩编号不为空，为空时提示重新输入
5. THE CLI SHALL 在交互式输入中，对无效输入给出具体的错误原因（如 `VIN 码必须为 17 位，当前输入 15 位`），而不是静默失败

### 需求 20：批量执行断点续跑

**用户故事：** 作为测试工程师，我希望批量跑充电订单时如果中途失败（网络断开、程序异常等），能从失败的那轮继续执行，不需要从头开始。

#### 验收标准

1. WHEN 批量执行中某一轮发生异常时，THE CLI SHALL 捕获异常，记录错误日志，并提示用户：`第 X 轮执行失败，[1] 重试本轮 [2] 跳过继续 [3] 停止执行`
2. THE CLI SHALL 在批量执行结束后打印执行摘要：成功 N 轮、失败 M 轮、跳过 K 轮
3. THE CLI SHALL 在每轮失败时不影响后续轮次的执行（除非用户选择停止）

### 需求 21：执行摘要与参数回显

**用户故事：** 作为测试工程师，我希望在执行前能看到即将使用的所有参数汇总，确认无误后再开始执行，避免参数配错浪费时间。

#### 验收标准

1. THE CLI SHALL 在收集完所有参数后、开始执行前，打印参数确认摘要，包含：
   - 当前环境（pre/test）
   - 桩编号、VIN、UID
   - 充电模式（即插即充/扫码）
   - SOC 参数（soc/bsoc/esoc）
   - 电池类型
   - 速度倍数
   - 循环次数（批量模式）
   - 场景特有参数（如满足度模式、身份盗用模式等）
2. THE CLI SHALL 在参数摘要后提示用户：`确认执行？[Y/n]`，用户输入 n 可返回重新输入参数
3. THE CLI SHALL 在日志文件开头记录本次执行的完整参数，方便事后复现

### 需求 22：MQTT 消息订阅与平台响应监听

**用户故事：** 作为测试工程师，我希望 CLI 工具能同时订阅平台下发的响应消息（如 carChkAck、chargEndAck、tradeAck 等），以便我能实时看到平台对我发送报文的响应，快速判断报文是否被正确处理。

#### 验收标准

1. THE CLI SHALL 在连接 MQTT 后自动订阅当前桩的 get Topic（`/{productKey}/{deviceName}/get`）和 RRPC request Topic（`/{productKey}/{deviceName}/rrpc/request/+`）
2. THE CLI SHALL 在收到平台响应消息时，实时打印响应内容（带颜色区分：发送用 `↑` 蓝色，接收用 `↓` 绿色）
3. THE CLI SHALL 将收到的响应消息同步记录到日志文件
4. THE CLI SHALL 支持 `--no-subscribe` 参数关闭订阅功能（某些场景不需要看响应）

### 需求 23：快捷操作与历史记录

**用户故事：** 作为每天都要用这个工具的测试工程师，我希望能快速重复上次的操作，不用每次都从菜单一步步选。

#### 验收标准

1. THE CLI SHALL 在每次执行后，将本次的完整操作参数保存到 `.last_run.json` 文件
2. THE CLI SHALL 在主菜单中新增选项 `[0] 重复上次操作`，读取 `.last_run.json` 并直接执行（执行前显示参数摘要供确认）
3. IF `.last_run.json` 不存在，THEN 选项 `[0]` 显示为灰色并提示"暂无历史记录"

### 需求 24：Ctrl+C 优雅退出

**用户故事：** 作为测试工程师，我希望在执行过程中按 Ctrl+C 能优雅退出，而不是看到一堆 Python 异常堆栈。

#### 验收标准

1. WHEN 用户在任意阶段按 Ctrl+C 时，THE CLI SHALL 捕获 KeyboardInterrupt，打印 `\n已中断，正在清理...`，断开 MQTT 连接后退出
2. THE CLI SHALL 在中断时将已执行的结果（如已完成的轮次、tradeID 等）写入日志文件，不丢失已有数据
3. THE CLI SHALL 在批量执行中断时打印已完成的轮次摘要（如 `已完成 5/10 轮`）

### 需求 25：配置文件中预填 test 环境真实值

**用户故事：** 作为测试工程师，我希望配置文件模板中 test 环境的参数是真实可用的值，不需要我自己去找。

#### 验收标准

1. THE 配置文件模板中 test 环境 SHALL 预填以下真实值（来源于现有 `mqtt_publish01.py` 的 CONFIGS）：
   - `pile`: `559847003`
   - `vin`: `TESTNUYCXPKWVTIZF`
   - `uid`: `1160057`
   - `mqtt_user`: `charge-private-mqtt`
   - `mqtt_pwd`: `0LZVRlmlD88Y`
   - `public_pile`: `XPeng_TEST_Charge`
   - `url_equip`: `http://thor.test.xiaopeng.local/api/xp-thor-asset/asset/equip/search`
   - `url_order`: `https://10.0.13.28:8553/biz/v5/chargeOrder/chargeOrderV2`
2. THE 配置文件模板中每个环境的每个参数旁 SHALL 有注释说明用途

### 需求 26：版本号显示

**用户故事：** 作为测试工程师，我希望能查看 CLI 工具的版本号，方便在反馈问题时告知使用的版本。

#### 验收标准

1. THE CLI SHALL 支持 `--version` 参数，打印当前版本号（如 `mqtt-cli v1.0.0`）
2. THE CLI SHALL 在主菜单标题栏显示版本号（如 `⚡ MQTT 充电桩模拟 CLI v1.0.0`）

### 需求 27：充电流程阶段暂停

**用户故事：** 作为测试工程师，我希望能让充电流程在某个阶段暂停指定时间（如停在"充电中"状态 5 分钟），以便模拟真实的充电时长，验证平台在充电过程中的实时数据展示。

#### 验收标准

1. THE CLI SHALL 支持 `--pause-at` 参数指定暂停阶段，可选值为：`charging`（充电中，发完 ycBMS 后暂停）、`complete`（充电完成，发完 chargEnd 后暂停）
2. THE CLI SHALL 支持 `--pause-duration` 参数指定暂停时长（秒），默认值为 `300`（5 分钟）
3. WHEN 暂停期间，THE CLI SHALL 每 30 秒（受 `--speed` 倍速影响）持续发送遥信（yx）报文保持桩在线状态
4. WHEN 暂停期间，THE CLI SHALL 显示倒计时提示（如 `充电中暂停，剩余 4:30，按回车提前结束`）
5. WHEN 用户在暂停期间按回车时，THE CLI SHALL 立即结束暂停，继续执行后续流程

### 需求 28：自定义 JSON 报文发送

**用户故事：** 作为测试工程师，我希望能直接粘贴一段 JSON 报文发送到 MQTT，以便发送工具未封装的报文类型或自定义字段值。

#### 验收标准

1. THE CLI SHALL 在"单条报文发送"子菜单中新增选项 `[12] 自定义 JSON`
2. WHEN 用户选择"自定义 JSON"时，THE CLI SHALL 提示用户粘贴完整的 JSON 字符串
3. THE CLI SHALL 校验输入是否为有效 JSON，无效时提示重新输入
4. THE CLI SHALL 将有效 JSON 发送到当前桩的 update Topic，并打印发送结果

### 需求 29：充电电量精确控制

**用户故事：** 作为测试工程师，我希望能精确指定充电电量（而不是随机生成），以便验证平台的结算金额计算是否正确。

#### 验收标准

1. THE CLI SHALL 支持 `--energy` 参数指定总充电电量（KWh），不指定时使用随机值
2. THE CLI SHALL 支持 `--energy1`~`--energy4` 参数分别指定尖/峰/平/谷四个时段的电量，不指定时按总电量随机分配
3. WHEN 用户同时指定 `--energy` 和 `--energy1`~`--energy4` 时，THE CLI SHALL 以分时段值为准，忽略总电量参数
4. THE CLI SHALL 在交互式模式中提示：`充电电量 (留空随机生成):`

### 需求 30：充电时长精确控制

**用户故事：** 作为测试工程师，我希望能精确指定充电时长和各时段时长，以便验证平台的占位费、延时费计算逻辑。

#### 验收标准

1. THE CLI SHALL 支持 `--charge-time` 参数指定总充电时长（分钟），默认值为 `3`
2. THE CLI SHALL 支持 `--time1`~`--time3` 参数分别指定尖/峰/平/谷时段的充电时长（分钟）
3. THE CLI SHALL 支持 `--occupy-time` 参数指定占位时长（秒），用于控制 trade 报文中 t5 字段（拔枪时间），默认随机 1300-2300 秒

### 需求 31：桩类型支持（直流/交流）

**用户故事：** 作为测试工程师，我希望 CLI 工具能区分直流桩和交流桩，以便模拟不同类型充电桩的报文差异。

#### 验收标准

1. THE CLI SHALL 支持 `--pile-type` 参数指定桩类型，可选值为 `dc`（直流，默认）和 `ac`（交流）
2. WHEN 桩类型为交流时，THE 充电桩模拟器 SHALL 在 bootNoti 报文中使用交流桩字段（`s_ver`、`h_ver`），而非直流桩字段（`s_ver1`、`s_ver2`、`h_ver1`、`h_ver2`）
3. WHEN 桩类型为交流时，THE 充电桩模拟器 SHALL 不发送 ycBMS 报文（BMS 数据仅直流桩上报）
4. THE 配置文件 SHALL 支持 `pile_type` 配置项

### 需求 32：多桩并行模拟

**用户故事：** 作为测试工程师，我希望能在一个 CLI 实例中同时模拟多个桩，以便测试平台在多桩并发场景下的处理能力。

#### 验收标准

1. THE CLI SHALL 在主菜单中新增选项 `[6] 多桩并行`
2. WHEN 用户选择"多桩并行"时，THE CLI SHALL 提示用户输入多个桩编号（逗号分隔）和充电模式
3. THE CLI SHALL 为每个桩创建独立的 Charger 实例，使用 Python 多线程并行执行充电流程
4. THE CLI SHALL 在每个桩的输出前加上桩编号前缀，方便区分（如 `[XPAC...0002] ▸ 1/7 上报空闲`）
5. THE CLI SHALL 在全部桩执行完成后打印汇总信息，列出每个桩的 tradeID/orderID

### 需求 33：场景编排（组合执行）

**用户故事：** 作为测试工程师，我希望能把多个操作编排成一个测试流程一键执行（如：先跑一次即插即充 → 再跑电池充检 → 最后模拟故障），以便自动化执行完整的测试场景。

#### 验收标准

1. THE CLI SHALL 支持从 YAML 文件读取场景编排脚本，按顺序执行多个操作
2. THE 编排脚本格式示例：
```yaml
name: "充电+充检完整流程"
steps:
  - action: run_plug
    params: { vin: "TEST2K0Y5JI4P6BC7", bsoc: 20, esoc: 90 }
  - action: scenario_battery_check
    params: { tradeID: "$prev.tradeID", vin: "$prev.vin", result: success }
  - action: fault_error
    params: { code: "E07" }
```
3. THE CLI SHALL 支持 `$prev.tradeID` 和 `$prev.orderID` 变量引用上一步的输出，实现步骤间数据传递
4. THE CLI SHALL 在主菜单中新增选项 `[7] 执行编排脚本`，提示用户输入脚本文件路径
5. THE CLI SHALL 在每个步骤执行前打印步骤名称和参数，执行后打印结果

### 需求 34：协议版本控制

**用户故事：** 作为测试工程师，我希望能指定充电桩的协议版本号，以便模拟不同版本桩的报文差异（如 v1.19 新增的 cdFlag/soc1 字段，旧版本桩不应包含这些字段）。

#### 验收标准

1. THE CLI SHALL 支持 `--protocol-ver` 参数指定协议版本号，默认值为 `119`（对应 v1.19）
2. WHEN 协议版本低于 119 时，THE 充电桩模拟器 SHALL 不在 ycBMS 报文中包含 `soc1` 和 `cdFlag` 字段
3. WHEN 协议版本低于 119 时，THE 充电桩模拟器 SHALL 不支持电池充检场景（cdProgress/pileProp）
4. THE 充电桩模拟器 SHALL 在 bootNoti 报文的 `p_ver` 字段中使用用户指定的协议版本号
5. THE 配置文件 SHALL 支持 `protocol_ver` 配置项

### 需求 35：充电过程 SOC 递增模拟

**用户故事：** 作为测试工程师，我希望充电过程中 ycBMS 报文的 SOC 值能从 bsoc 逐步递增到 esoc，而不是固定一个值，以便更真实地模拟充电过程，验证平台的实时 SOC 展示。

#### 验收标准

1. WHEN 充电中阶段发送多条 ycBMS 报文时，THE 充电桩模拟器 SHALL 将 SOC 值从 `bsoc` 线性递增到 `esoc`
2. THE 充电桩模拟器 SHALL 根据发送的 ycBMS 报文总数均匀分配 SOC 增量（如 bsoc=20, esoc=90, 发 4 条，则 SOC 依次为 20, 43, 67, 90）
3. THE 充电桩模拟器 SHALL 同步递减 `remainTime`（剩余充电时间），从初始值递减到 0

### 需求 36：bootNoti 桩启动上报

**用户故事：** 作为测试工程师，我希望充电流程开始前能先发送 bootNoti（桩启动通知）报文，以便模拟桩从上电到充电的完整流程。

#### 验收标准

1. THE CLI SHALL 支持 `--boot` 参数（布尔开关），启用后在充电流程开始前先发送 bootNoti 报文，默认关闭
2. THE bootNoti 报文 SHALL 包含桩类型（dc/ac）、协议版本号、供应商、固件版本等字段
3. THE CLI SHALL 在交互式模式中提示：`是否先发送桩启动通知 (bootNoti)? [y/N]:`

### 需求 37：敏感信息保护

**用户故事：** 作为测试工程师，我希望配置文件中的 MQTT 密码等敏感信息不以明文存储，避免配置文件泄露导致安全风险。

#### 验收标准

1. THE CLI SHALL 支持通过环境变量覆盖配置文件中的敏感字段（如 `MQTT_PWD_PRE`、`MQTT_PWD_TEST`）
2. THE 配置文件模板 SHALL 在密码字段旁注释说明：`# 建议通过环境变量 MQTT_PWD_PRE 设置，此处留空`
3. THE CLI SHALL 按以下优先级读取敏感信息：环境变量 > 配置文件 > 内置默认值
4. THE CLI SHALL 在日志文件中对密码字段做脱敏处理（显示为 `***`）

### 需求 38：充电中持续上报遥测数据

**用户故事：** 作为测试工程师，我希望在充电中阶段（特别是使用 `--pause-at charging` 暂停时），CLI 能持续周期性上报 ycBMS 和 ycMeas 数据，而不是只发一条，以便更真实地模拟充电过程中的持续数据上报。

#### 验收标准

1. WHEN 充电中阶段暂停时（`--pause-at charging`），THE 充电桩模拟器 SHALL 每隔 `--bms-interval` 秒（默认 10 秒，受 `--speed` 倍速影响）发送一条 ycBMS 报文
2. THE 充电桩模拟器 SHALL 在持续上报的 ycBMS 报文中递增 SOC 值（需求 35）
3. THE 充电桩模拟器 SHALL 每隔 `--meas-interval` 秒（默认 30 秒）发送一条 ycMeas 报文，累加充电电量
4. THE 充电桩模拟器 SHALL 每隔 30 秒发送一条 yx 报文（status=1）保持桩在线
