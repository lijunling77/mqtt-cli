# MQTT 充电桩模拟工具

## 描述
通过命令行调用 MQTT 充电桩模拟 CLI 工具，支持充电流程模拟、场景脚本、异常状态模拟等功能。

## 使用方式
当用户提到充电桩模拟、跑充电订单、充电小结、电池充检、满足度、身份盗用、异常模拟、故障模拟等关键词时，使用以下命令行工具。

## 可用命令

### 即插即充
```bash
python mqtt_cli.py run plug --env pre --pile <桩编码> --vin <VIN码>
```

### 扫码充电
```bash
python mqtt_cli.py run scan --env pre --pile <桩编码> --vin <VIN码> --uid <用户UID>
```

### 批量跑充电订单
```bash
python mqtt_cli.py run plug --loop <次数> --pile <桩编码>
python mqtt_cli.py run scan --loop <次数> --pile <桩编码> --uid <用户UID>
```

### 充电小结
```bash
python mqtt_cli.py scenario summary --pile <桩编码> --vin <VIN码> --uid <用户UID>
```

### 充电需求功率满足度
```bash
# 模式: normal(需求低预期高), mismatch(车桩错配), shunt(同车分流/桩故障)
# 支持逗号分隔多个模式
python mqtt_cli.py scenario satisfaction --pile <桩编码> --vin <VIN码> --mode normal
python mqtt_cli.py scenario satisfaction --mode normal,mismatch,shunt
```

### 身份盗用
```bash
# 模式: normal(正常), bat-type(电池类型不一致), ah-bias(额定容量偏差), kwh-bias(标定能量偏差)
python mqtt_cli.py scenario identity-theft --pile <桩编码> --vin <VIN码> --mode bat-type
```

### 异常状态模拟
```bash
# 故障
python mqtt_cli.py fault error --pile <桩编码> --code E07
# 急停
python mqtt_cli.py fault estop --pile <桩编码>
# 升级中
python mqtt_cli.py fault upgrading --pile <桩编码>
```

### 发送自定义报文
```bash
python mqtt_cli.py send --pile <桩编码> --json '{"msg":"yx","cif":1,"status":0}'
```

## 默认参数
- 环境: pre
- 桩编码: XPAC2017YS03240002
- VIN: TEST2K0Y5JI4P6BC7
- UID: 8102985
- 速度倍数: 2.0

## 环境说明
- `--env pre`: 预发环境 (默认)
- `--env test`: 测试环境

## 注意事项
- 电池充检场景需要交互式操作（在 APP 执行充检），建议使用交互式菜单模式：`python mqtt_cli.py`
- 满足度场景发完 BMS 后会询问是否继续发其他模式或结束充电
- 所有命令执行后会打印 tradeID 和 orderID
