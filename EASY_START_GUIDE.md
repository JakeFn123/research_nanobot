# nanobot 中文易懂上手指南

这份指南用最直白的方式解释 nanobot：它是什么、能做什么、怎么快速用起来。

如果你要使用本项目的科研多智能体完整流程，请看：
- `docs/RESEARCH_NANOBOT_USER_MANUAL_ZH.md`
- `docs/DOCUMENTATION_INDEX_ZH.md`（中文文档总入口）

## 1）nanobot 是什么？

nanobot 是一个轻量级个人 AI 助手框架。

你可以把它理解成：
- 一个可在命令行直接对话的 AI 助手（`nanobot agent`）
- 一个可接入聊天平台的网关服务（`nanobot gateway`）
- 一套内置工具能力（读写文件、执行命令、网页搜索/抓取、定时任务、子代理）
- 一套可长期积累的工作区记忆与配置文件

一句话：它是“可以本地运行、可定制、可接入 Telegram/Discord/WhatsApp 等平台”的 Agent 运行框架。

## 2）它在内部是怎么工作的？

当你发出一条消息时，nanobot 的处理流程是：
1. 接收消息（来自 CLI 或聊天平台）
2. 构建上下文：
- 系统身份与运行时信息
- 工作区引导文件（`AGENTS.md`、`SOUL.md`、`USER.md`、`TOOLS.md`）
- 记忆文件（`memory/MEMORY.md`、`memory/HISTORY.md`）
- 可用技能（skills）
3. 调用 LLM 得到回复（必要时触发工具调用）
4. 执行工具调用并循环，直到得到最终答案
5. 将结果发回 CLI 或聊天平台

核心代码位置：
- `nanobot/agent/loop.py`：Agent 主循环
- `nanobot/channels/manager.py`：渠道管理与消息发送重试
- `nanobot/cron/service.py`：定时任务服务
- `nanobot/agent/memory.py`：记忆整合与持久化

## 3）最重要的目录和文件

默认运行目录：
- 配置：`~/.nanobot/config.json`
- 工作区：`~/.nanobot/workspace`

你最常会改的文件：
- `SOUL.md`：助手人格与价值观
- `USER.md`：你的个人偏好和背景
- `TOOLS.md`：工具行为说明
- `HEARTBEAT.md`：周期任务清单
- `memory/MEMORY.md`：长期记忆
- `memory/HISTORY.md`：可检索历史日志
- `skills/`：你的自定义技能

## 4）从源码安装（你现在这个仓库）

你已经克隆到了：
- `/Users/jakefan/nanobot`

推荐安装步骤：

```bash
cd /Users/jakefan/nanobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

验证安装：

```bash
nanobot --version
```

## 5）最快 2~3 分钟跑起来

### 第一步：初始化

```bash
nanobot onboard
```

想要交互式引导可用：

```bash
nanobot onboard --wizard
```

### 第二步：配置模型

编辑 `~/.nanobot/config.json`，至少设置：
- 一个 provider 的 API key
- 默认模型（建议同时指定 provider）

示例（OpenRouter）：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxxx"
    }
  },
  "agents": {
    "defaults": {
      "provider": "openrouter",
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
```

### 第三步：开始对话

```bash
nanobot agent
```

单条命令模式：

```bash
nanobot agent -m "帮我总结这个项目"
```

## 6）两种运行方式

### 方式 A：CLI 对话模式

适合终端直接问答：

```bash
nanobot agent
```

### 方式 B：网关模式（聊天平台 + 周期任务）

适合接入 Telegram/Discord 等平台，并启用 heartbeat 周期执行：

```bash
nanobot gateway
```

## 7）接入聊天平台

nanobot 支持多个渠道：Telegram、Discord、WhatsApp、Weixin、Feishu、DingTalk、Slack、Matrix、Email、QQ、Wecom、Mochat。

典型流程：
1. 在 `~/.nanobot/config.json` 的 `channels` 中配置对应渠道
2. 对于 QR/OAuth 类渠道，执行：

```bash
nanobot channels login <channel>
```

3. 启动网关：

```bash
nanobot gateway
```

查看渠道状态：

```bash
nanobot channels status
```

## 8）工具与安全策略

默认可用工具包括：
- 文件系统工具（读/写/编辑/列目录）
- Shell 执行
- Web 搜索与网页抓取
- 定时与消息工具

你应重点了解的安全开关：
- `tools.restrictToWorkspace`：启用后，工具文件访问会限制在工作区内

## 9）自动化能力

nanobot 有两类“定时/自动化”方式：

1. Heartbeat 清单（`HEARTBEAT.md`）
- 网关默认每 30 分钟检查一次
- 有任务就执行，并把结果发到你最近活跃的聊天渠道

2. Cron 任务（工具创建）
- 持久化保存到 `cron/jobs.json`
- 支持一次性、固定间隔、cron 表达式

## 10）快速定制助手行为

最有效的 4 个入口：
1. `SOUL.md`：定义助手风格、语气、行为边界
2. `USER.md`：填写你的语言、技术水平、工作场景
3. `AGENTS.md`（若存在）：高优先级运行规则
4. `skills/你的技能/SKILL.md`：沉淀可复用工作流

这些文件会进入上下文，所以你改完后行为会立即变化。

## 11）日常命令速查

```bash
nanobot onboard
nanobot agent
nanobot agent -m "Hello"
nanobot gateway
nanobot status
nanobot channels status
nanobot channels login <channel>
nanobot provider login openai-codex
```

## 12）常见问题

- `nanobot: command not found`
  - 先激活虚拟环境，再执行 `pip install -e .`
- 模型无响应
  - 检查 `~/.nanobot/config.json` 的 key、provider、model 是否匹配
- 渠道发不出去
  - 先看 `nanobot channels status`，再看网关日志
- 想开多个互相隔离实例
  - 用 `-c <config>` + `-w <workspace>` 指定不同配置与工作区

## 13）建议的上手路径（第一次用）

1. 执行 `nanobot onboard --wizard`
2. 配好一个 provider key + model
3. 用 `nanobot agent` 先做一次本地目录任务
4. 修改 `~/.nanobot/workspace/USER.md` 让风格更贴合你
5. 先接入一个渠道（一般 Telegram 最快）
6. 启动 `nanobot gateway`
7. 在 `HEARTBEAT.md` 加一个周期任务

走完这一套，你就会对 nanobot 的完整生命周期有清晰认知。
