# MQTT 充电桩模拟 — CLI 命令速查

## 充电流程
```bash
python mqtt_cli.py run plug                                    # 即插即充
python mqtt_cli.py run scan --uid 8102985                      # 扫码充电
python mqtt_cli.py run plug --loop 5                           # 批量 5 次
python mqtt_cli.py run plug --env test                         # test 环境
```

## 场景脚本
```bash
python mqtt_cli.py scenario summary --uid 8102985              # 充电小结
python mqtt_cli.py scenario satisfaction --mode normal          # 满足度-正常
python mqtt_cli.py scenario satisfaction --mode mismatch        # 满足度-错配
python mqtt_cli.py scenario satisfaction --mode shunt           # 满足度-分流
python mqtt_cli.py scenario identity-theft --mode normal        # 身份盗用-正常
python mqtt_cli.py scenario identity-theft --mode bat-type      # 身份盗用-电池类型
python mqtt_cli.py scenario identity-theft --mode ah-bias       # 身份盗用-容量偏差
python mqtt_cli.py scenario identity-theft --mode kwh-bias      # 身份盗用-能量偏差
```

## 异常模拟
```bash
python mqtt_cli.py fault error --code E07                      # 故障
python mqtt_cli.py fault estop                                 # 急停
python mqtt_cli.py fault upgrading                             # 升级中
```

## 批量编排
```bash
python run_plan.py test_plans/daily_smoke.yaml                 # 冒烟测试
python run_plan.py test_plans/full_regression.yaml             # 全量回归
python run_plan.py test_plans/fault_tests.yaml                 # 异常测试
python run_plan.py test_plans/scenario_tests.yaml              # 场景测试
python run_plan.py test_plans/charging_flow.yaml               # 充电流程
```

## 交互式菜单
```bash
python mqtt_cli.py                                             # 进入菜单
```
