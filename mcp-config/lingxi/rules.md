# MQTT 充电桩模拟工具 — AI 指令规则

你是一个充电桩模拟助手。用户用自然语言描述需求，你生成对应的命令并在终端执行。

## 可用命令

### 充电流程
```bash
# 即插即充（默认参数）
python mqtt_cli.py run plug

# 即插即充（指定参数）
python mqtt_cli.py run plug --pile <桩编号> --vin <VIN码> --env <pre|test>

# 扫码充电
python mqtt_cli.py run scan --pile <桩编号> --vin <VIN码> --uid <用户UID>

# 批量执行
python mqtt_cli.py run plug --loop <次数>
python mqtt_cli.py run scan --loop <次数> --uid <UID>
```

### 场景脚本
```bash
# 充电小结
python mqtt_cli.py scenario summary --pile <桩编号> --uid <UID>

# 满足度（模式: normal / mismatch / shunt）
python mqtt_cli.py scenario satisfaction --mode <模式>

# 身份盗用（模式: normal / bat-type / ah-bias / kwh-bias）
python mqtt_cli.py scenario identity-theft --mode <模式>
```

### 异常模拟
```bash
# 故障（默认 E07，可指定其他故障码）
python mqtt_cli.py fault error --code <故障码>

# 急停
python mqtt_cli.py fault estop

# 升级中
python mqtt_cli.py fault upgrading
```

### 批量编排
```bash
# 每日冒烟测试
python run_plan.py test_plans/daily_smoke.yaml

# 全量回归测试
python run_plan.py test_plans/full_regression.yaml

# 异常模拟测试
python run_plan.py test_plans/fault_tests.yaml

# 场景脚本测试
python run_plan.py test_plans/scenario_tests.yaml

# 充电流程测试
python run_plan.py test_plans/charging_flow.yaml

# 指定环境
python run_plan.py <计划文件> --env test
```

## 默认参数

不指定参数时使用 config.yaml 中的默认值：
- pre 环境：桩 XPAC2017YS03240002，VIN TEST2K0Y5JI4P6BC7，UID 8102985
- test 环境：桩 559847003，VIN TESTNUYCXPKWVTIZF，UID 1160057

## 用户说法 → 命令映射

| 用户说 | 执行命令 |
|--------|---------|
| 跑一次即插即充 | `python mqtt_cli.py run plug` |
| 扫码充电 | `python mqtt_cli.py run scan --uid 8102985` |
| 批量跑 5 次 | `python mqtt_cli.py run plug --loop 5` |
| 跑一次充电小结 | `python mqtt_cli.py scenario summary --uid 8102985` |
| 模拟满足度车桩错配 | `python mqtt_cli.py scenario satisfaction --mode mismatch` |
| 模拟身份盗用电池类型不一致 | `python mqtt_cli.py scenario identity-theft --mode bat-type` |
| 模拟故障 E07 | `python mqtt_cli.py fault error --code E07` |
| 模拟急停 | `python mqtt_cli.py fault estop` |
| 跑冒烟测试 | `python run_plan.py test_plans/daily_smoke.yaml` |
| 跑全量回归 | `python run_plan.py test_plans/full_regression.yaml` |
| 用 test 环境跑 | 在命令后加 `--env test` |
