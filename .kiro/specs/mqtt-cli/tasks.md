# 任务列表

## 1. 消息模板扩展（mqtt_msg_dc.py）

- [x] 1.1 在 `MqttMsgDC` 类中新增 `publish_pileProp` 方法，生成桩属性数据消息（含 dev 对象：vendor、ratedPower、maxOutVol、minOutVol、maxOutCur、minOutCur、cdEn）
- [x] 1.2 在 `MqttMsgDC` 类中新增 `publish_cdProgress` 方法，生成电池充检进度消息（state=100 时包含额外字段：tradeID、vin、beginTime、endTime、bp_r_cur、beginSoC、endSoC、errcode、errmsg）
- [x] 1.3 扩展 `publish_ycBMS` 方法，新增 `soc1` 和 `cdFlag` 可选参数（传入时包含在 JSON 中，不传时不包含）

## 2. 环境配置管理（mqtt_cli.py）

- [x] 2.1 在 `mqtt_cli.py` 中定义 `ENV_CONFIG` 字典，包含 `pre` 和 `test` 两套环境配置（MQTT 地址、端口、用户名、密码、productKey、HTTP 接口地址）
- [x] 2.2 移除现有硬编码的全局常量（MQTT_IP、MQTT_PORT 等），改为从 `ENV_CONFIG` 读取
- [x] 2.3 新增无效环境名校验逻辑：不存在时输出错误提示并列出可用环境名，以非零退出码退出

## 3. Charger 类改造（mqtt_cli.py）

- [x] 3.1 改造 `Charger.__init__`，新增 `env` 参数，从 `ENV_CONFIG[env]` 读取配置初始化 MQTT 连接
- [x] 3.2 改造 `plug_charge` 方法，返回 `(tradeID, orderID)` 元组（即插即充 orderID 为空字符串）
- [x] 3.3 改造 `scan_charge` 方法，返回 `(tradeID, orderID)` 元组

## 4. 场景方法实现（mqtt_cli.py - Charger 类）

- [x] 4.1 实现 `scenario_summary` 方法：执行完整充电流程，充电中阶段发送至少 4 条不同功率参数的 ycBMS 报文（按 SUMMARY_BMS_SEQUENCE），支持 `--reason` 参数，完成后返回 (tradeID, orderID)
- [x] 4.2 实现 `scenario_battery_check` 方法：发送 pileProp(cdEn=1) → ycBMS(cdFlag=2, soc1) → cdProgress(state 1→2/3/4→100)，支持充检结果选择和 `--interval` 参数
- [x] 4.3 实现 `scenario_satisfaction` 方法：执行完整充电流程，按 `--mode`（normal/mismatch/shunt）使用预设 ycBMS 参数或自定义参数，支持 `--bms-count` 参数
- [x] 4.4 实现 `scenario_identity_theft` 方法：执行即插即充流程，按 `--mode`（normal/bat-type/ah-bias/kwh-bias）使用预设电池参数，在 carChk 和 starting(state=5) 中发送对应参数

## 5. 异常模拟方法实现（mqtt_cli.py - Charger 类）

- [x] 5.1 实现 `fault_error` 方法：发送 yx 消息（error=1, errcode=用户指定），支持 `--repeat` 和 `--interval` 参数
- [x] 5.2 实现 `fault_estop` 方法：发送 yx 消息（error=1, errcode=E05），支持 `--repeat` 和 `--interval`
- [x] 5.3 实现 `fault_upgrading` 方法：发送 yx 消息（status=6），支持 `--repeat` 和 `--interval`
- [x] 5.4 实现 `fault_start_fail` 方法：发送 starting 消息（state=255, reason=用户指定），支持 `--reason` 和 `--errcode` 参数
- [x] 5.5 实现 `fault_gun_lock` 方法：发送锁枪 yx 消息（满足触发条件 status=2/5, yx1=1, yx3=1, error=1, errcode=E71），支持 `--repeat` 和 `--interval`
- [x] 5.6 实现 `fault_offline` 方法：发送 bootNoti → 断开 MQTT → 等待 duration 秒 → 重连 → 发送 olTrade，支持 `--duration` 参数

## 6. CLI 入口重构（mqtt_cli.py - main 函数）

- [x] 6.1 重构 `main` 函数，使用 argparse 子命令结构（run plug/scan、scenario summary/battery-check/satisfaction/identity-theft、fault error/estop/upgrading/start-fail/gun-lock/offline），支持全局参数 `--env`、`--pile`、`--cif`、`--speed`
- [x] 6.2 实现 `interactive_menu` 函数：无子命令时显示交互式主菜单（4 个选项），场景脚本和异常模拟有子菜单，收集用户输入参数并提供默认值
- [x] 6.3 实现批量执行逻辑：`--loop` 参数控制循环次数，每轮打印轮次信息，轮间等待 5/speed 秒，全部完成后打印总结
- [x] 6.4 实现执行结果打印：每轮/每次充电流程完成后醒目打印 tradeID 和 orderID，启动时打印当前模式、桩编号、VIN、速度倍数等关键参数

## 7. 配置文件与依赖管理

- [x] 7.1 创建 `config.yaml` 默认配置文件模板，包含 environments（pre/test 完整配置）、defaults（通用默认参数）、battery（电池/BMS 参数）三个分组，每个字段带中文注释
- [x] 7.2 在 `mqtt_cli.py` 中实现 ConfigManager，支持加载 config.yaml、环境变量覆盖敏感信息、多层参数优先级合并（命令行 > 交互输入 > 配置文件 > 内置默认值）
- [x] 7.3 实现首次运行时检测 config.yaml 不存在则提示生成默认模板
- [x] 7.4 创建 `requirements.txt`，包含 paho-mqtt、requests、fake-useragent、pyyaml

## 8. 单条报文发送与自定义 JSON

- [x] 8.1 在主菜单新增 `[5] 单条报文发送`，实现报文类型子菜单（yx/ycBMS/ycMeas/ycAnalog/starting/chargEnd/trade/carChk/bootNoti/pileProp/cdProgress/自定义JSON），每种类型交互式收集关键参数并发送
- [x] 8.2 实现自定义 JSON 报文发送：用户粘贴 JSON 字符串，校验格式后发送到 update Topic

## 9. 新手引导与文档

- [x] 9.1 创建 `README.md`，包含环境准备、快速开始（3步上手）、菜单结构总览、每个模式的使用示例、配置文件说明、常见问题 FAQ
- [x] 9.2 在交互式菜单每个选项和参数输入处添加中文说明和示例值

## 10. 执行体验优化

- [x] 10.1 实现执行完成后返回主菜单循环（按回车返回，输入 q 退出），保持 MQTT 连接不断开
- [x] 10.2 实现参数回显确认：收集完参数后打印摘要，用户确认后再执行
- [x] 10.3 实现参数输入校验：VIN 17位、SOC 0-100、bsoc < esoc、bat 3/6、pile 非空，无效时给出具体错误原因
- [x] 10.4 实现 Ctrl+C 优雅退出：捕获 KeyboardInterrupt，打印已完成摘要，断开 MQTT 连接
- [x] 10.5 实现版本号显示：`--version` 参数和主菜单标题栏显示版本号

## 11. 日志与历史记录

- [x] 11.1 实现 DualLogger：同时输出到终端（彩色）和日志文件（logs/{YYYYMMDD_HHmmss}.log），密码脱敏
- [x] 11.2 实现快捷重复操作：每次执行后保存参数到 `.last_run.json`，主菜单 `[0] 重复上次操作`

## 12. MQTT 响应监听

- [x] 12.1 实现自动订阅 get Topic 和 rrpc request Topic，收到平台响应时实时打印（绿色 ↓）并记录到日志

## 13. 批量执行增强

- [x] 13.1 实现批量执行断点续跑：某轮失败时提示重试/跳过/停止，执行结束打印摘要（成功N轮/失败M轮/跳过K轮）

## 14. 充电流程增强

- [x] 14.1 实现充电过程 SOC 递增模拟：ycBMS 的 SOC 从 bsoc 线性递增到 esoc，remainTime 同步递减
- [ ] 14.2 (可选-后续版本) 实现充电流程阶段暂停（`--pause-at charging/complete`）：暂停期间持续发送 yx/ycBMS/ycMeas 心跳，显示倒计时，按回车提前结束
- [ ] 14.3 (可选-后续版本) 实现充电电量精确控制（`--energy`、`--energy1`~`--energy4`）和充电时长精确控制（`--charge-time`、`--occupy-time`）
- [x] 14.4 实现 bootNoti 桩启动上报（`--boot` 开关），充电前可选发送 bootNoti 报文

## 15. 高级功能

- [ ] 15.1 (可选-后续版本) 实现桩类型支持（`--pile-type dc/ac`）：交流桩使用不同的 bootNoti 字段，不发 ycBMS
- [ ] 15.2 (可选-后续版本) 实现多桩并行模拟：主菜单 `[6] 多桩并行`，多个桩编号逗号分隔，多线程并行执行，输出带桩编号前缀
- [ ] 15.3 (可选-后续版本) 实现场景编排：主菜单 `[7] 执行编排脚本`，从 YAML 文件读取多步操作，支持 `$prev.tradeID` 变量传递
- [ ] 15.4 (可选-后续版本) 实现协议版本控制（`--protocol-ver`）：低版本不包含 soc1/cdFlag 字段，不支持充检场景
- [x] 15.5 实现敏感信息保护：环境变量覆盖密码字段，日志中密码显示为 `***`

## 16. 打包发布

- [x] 16.1 创建 PyInstaller 打包配置，支持 `pyinstaller --onefile mqtt_cli.py` 生成独立 exe
- [x] 16.2 在 README.md 中补充打包说明和使用者说明（下载 exe + config.yaml → 双击运行）
