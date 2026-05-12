# nsh — Natural Shell

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**nsh** 是一个命令行工具，能将自然语言（中文 / 英文）翻译为 Ubuntu shell 命令，
并安全地执行。基于 DeepSeek API 驱动。

## 特性

- **自然语言 → Shell 命令** — 用日常语言描述想做的事，自动生成命令
- **上下文衔接** — 记住最近的操作，"安装 nginx" 之后说 "启动它" 就能识别
- **Rich 命令预览** — 语法高亮 + 面板展示，安全命令绿框，危险命令红框
- **危险命令拦截** — 四重严重度分级（LOW / MEDIUM / HIGH / CRITICAL），危险命令需确认
- **一键执行** — 支持 `--yes` 跳过确认直接执行

## 安装

### 前置要求

- Python 3.13+
- Ubuntu / Debian 系统

```bash
# 克隆仓库
git clone https://github.com/CoolLiang/nsh.git
cd nsh

# 安装
pip install -e .
```

### 配置 API Key

```bash
# 方式一：环境变量（推荐）
export ANTHROPIC_API_KEY="sk-your-key-here"

# 方式二：配置文件
nsh config set api_key sk-your-key-here
```

默认使用 DeepSeek 代理地址，如需更换：
```bash
nsh config set base_url https://api.deepseek.com/anthropic
```

## 使用方法

### `nsh ask` — 翻译命令（不执行）

```bash
nsh ask "列出所有本周修改的 PDF 文件"
nsh ask "查找占用 CPU 最高的 5 个进程"
nsh ask "安装 docker 并启动"
```

输出示例：

```
┏━━━━━━━━━━━━━━━━━━━━━ 生成的命令 ━━━━━━━━━━━━━━━━━━━━━┓
┃                                                        ┃
┃  find . -name "*.pdf" -mtime -7                        ┃
┃                                                        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### `nsh` — 翻译并执行

```bash
nsh "安装 nginx"
nsh --yes "列出当前目录的大文件"
```

流程：`翻译 → 展示命令 → 确认 → 执行`

```
┏━━━━━━━━━━━━━━━━━━━━━ 生成的命令 ━━━━━━━━━━━━━━━━━━━━━┓
┃  sudo apt install -y nginx                              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

是否执行此命令？ [y/N]: y

执行中…
✓ 执行成功 (exit code: 0)
```

### 选项

| 选项 | 说明 |
|---|---|
| `--yes` `-y` | 跳过确认，直接执行 |
| `--model` `-m` | 指定模型（覆盖配置） |
| `--no-session` | 不注入会话上下文 |
| `--interactive` `-i` | 交互模式执行（保留终端，用于 vim/less 等） |

### 上下文衔接示例

```bash
$ nsh "安装 nginx"
→ sudo apt install -y nginx           # 执行成功，记录到会话

$ nsh "启动它"
→ sudo systemctl start nginx          # "它" → nginx（从会话推断）
```

### 危险命令拦截

当命令包含危险操作时，红色面板警告：

```
┏━━━━━━━━━━━━━━━━━━━━━ ⚠ 危险命令 ━━━━━━━━━━━━━━━━━━━━━┓
┃  rm -rf / --no-preserve-root                           ┃
┃                                                        ┃
┃  🚫 检测到以下危险模式：                                ┃
┃    • rm -rf / — 递归删除根目录                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┏━━━━━━━━━━━━━━━━━━━━ ⚠ 安全警告 ━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 此命令包含危险操作，执行可能导致数据丢失或系统损坏。    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

确定要执行此危险命令吗？ [y/N]: y
⚠ 此命令可能造成不可逆的系统损坏！
再次确认：你真的要执行吗？ [y/N]: n

已取消执行。
```

### `nsh session` — 管理会话历史

```bash
nsh session              # 查看历史
nsh session --clear      # 清除历史
```

### `nsh config` — 管理配置

```bash
nsh config get                # 查看所有配置
nsh config get base_url       # 查看单项
nsh config set model deepseek-v4-flash
nsh config set auto_execute true
nsh config path               # 配置文件路径
nsh config reset              # 恢复默认值
```

### 配置文件

位置：`~/.config/nsh/config.json`

```json
{
  "api_key": "sk-xxx",
  "base_url": "https://api.deepseek.com/anthropic",
  "model": "deepseek-v4-flash",
  "max_tokens": 500,
  "auto_execute": false,
  "safe_mode": true,
  "language": "zh"
}
```

## 安全机制

| 级别 | 示例 | 确认流程 |
|---|---|---|
| LOW | `apt autoremove` | 仅记录 |
| MEDIUM | `shutdown`, `reboot` | 需确认 |
| HIGH | `rm -rf *`, `curl \| bash` | 需确认 |
| CRITICAL | `rm -rf /`, fork bomb, `dd of=/dev/sda` | **双重确认** |

共检测 **34 种**危险模式，包括：
- 磁盘破坏（`rm -rf /`、`dd`、`mkfs`、`fdisk`）
- 远程代码执行（`curl \| bash`、`wget \| sh`）
- 系统关机（`shutdown`、`reboot`、`halt`）
- Fork bomb（`:(){ :|:& };:`）
- 系统文件覆写（`/etc/passwd`、`/etc/shadow`、`/boot/`）
- 批量杀进程（`kill -9 -1`、`killall`）

## 项目结构

```
nsh/
├── __init__.py       # 包初始化
├── main.py           # Typer CLI 入口 + Rich 面板渲染
├── config.py         # ~/.config/nsh/config.json 管理
├── translator.py     # DeepSeek API 调用（NL → 命令）
├── executor.py       # 安全检测 + 命令执行
└── session.py        # 会话缓存（上下文记忆）
```

## 开发

```bash
pip install -e ".[dev]"    # 安装开发依赖
python -m nsh.main --help  # 本地调试
```

## License

MIT © CoolLiang
