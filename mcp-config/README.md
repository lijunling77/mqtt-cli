# 🤖 AI 工具接入充电桩模拟 — MCP 配置指南

本项目提供了 MCP Server（`mqtt_mcp_server.py`），支持在各种 AI 编程工具中用自然语言操作充电桩模拟。

## 前置准备

1. 安装 Python 3.8+
2. 克隆项目并安装依赖：
```bash
git clone http://gitlab.xiaopeng.local:18080/charge-testing/mqtt-cli.git
cd mqtt-cli
pip install -r requirements.txt
```

---

## Cursor

1. 在项目根目录创建 `.cursor/mcp.json`（或复制 `mcp-config/cursor/mcp.json`）
2. 修改内容，将 `cwd` 改为项目实际路径：

```json
{
  "mcpServers": {
    "mqtt-charger": {
      "command": "python",
      "args": ["mqtt_mcp_server.py"],
      "cwd": "E:/mqtt-cli"
    }
  }
}
```

3. 重启 Cursor，在聊天中即可使用：
   - "跑一次即插即充"
   - "模拟桩故障 E07"

---

## Claude Desktop

1. 打开配置文件：
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

2. 添加以下内容（修改路径为实际路径）：

```json
{
  "mcpServers": {
    "mqtt-charger": {
      "command": "python",
      "args": ["E:/mqtt-cli/mqtt_mcp_server.py"],
      "cwd": "E:/mqtt-cli"
    }
  }
}
```

3. 重启 Claude Desktop，在对话中即可使用。

---

## VS Code + GitHub Copilot

需要 VS Code 1.99+ 且启用了 Copilot Chat。

1. 在项目根目录创建 `.vscode/mcp.json`（或复制 `mcp-config/vscode/mcp.json`）
2. 修改内容：

```json
{
  "servers": {
    "mqtt-charger": {
      "type": "stdio",
      "command": "python",
      "args": ["mqtt_mcp_server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

3. 在 Copilot Chat 中使用 Agent 模式即可调用。

---

## Kiro

项目已内置配置（`.kiro/settings/mcp.json`），用 Kiro 打开项目文件夹即可直接使用。

---

## 灵犀 / 其他支持 MCP 的工具

灵犀配置文件在 `mcp-config/lingxi/` 目录下，提供三种接入方案：

| 文件 | 适用场景 |
|------|---------|
| `mcp.json` | 灵犀支持 MCP 协议时，配置此文件即可用自然语言调用 |
| `rules.md` | 灵犀支持自定义规则/提示词时，导入此文件作为 AI 指令规则 |
| `cli-cheatsheet.md` | 灵犀只支持终端命令时，参考此速查卡 |

如果工具支持 MCP stdio 协议，配置方式类似：
- **command**: `python`
- **args**: `["mqtt_mcp_server.py"]`（或完整路径）
- **cwd**: 项目根目录路径

---

## 可用指令

配置完成后，在 AI 聊天中用自然语言即可操作：

| 说法 | 功能 |
|------|------|
| 跑一次即插即充 | 执行即插即充完整流程 |
| 扫码充电，UID 8102985 | 执行扫码充电流程 |
| 跑一次充电小结 | 执行充电小结场景 |
| 模拟满足度，车桩错配 | 执行满足度场景 |
| 模拟身份盗用，电池类型不一致 | 执行身份盗用场景 |
| 模拟桩故障 E07 | 发送故障报文 |
| 模拟急停 | 发送急停报文 |
| 模拟升级中 | 发送升级中报文 |
| 模拟启动失败 | 发送启动失败报文 |
| 模拟锁枪异常 | 发送锁枪报文 |

可选参数：
- 指定桩：`桩 XPAC2017YS03240002`
- 指定 VIN：`VIN TEST2K0Y5JI4P6BC7`
- 指定环境：`环境 test`

不指定参数时使用 `config.yaml` 中的默认值。

---

## 常见问题

**Q: MCP Server 连接失败？**
A: 确认 Python 路径正确，且已安装依赖（`pip install -r requirements.txt`）。在命令行手动运行 `python mqtt_mcp_server.py` 看是否有报错。

**Q: 工具里看不到充电桩相关的功能？**
A: 检查 MCP 配置文件路径和格式是否正确，重启 AI 工具后重试。

**Q: 可以多人同时使用吗？**
A: 可以。每次调用会创建独立的 MQTT 连接，互不影响。但注意不要同时对同一个桩编号执行冲突操作。
