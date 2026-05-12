"""Natural language → shell command translation via Anthropic API."""

from __future__ import annotations

from anthropic import Anthropic
from anthropic.types import TextBlock

from nsh.config import Config
from nsh.session import Session

_SYSTEM_PROMPT = """你是一个 Ubuntu shell 命令生成器。根据用户的自然语言描述，生成对应的 shell 命令。

规则：
- 只输出命令本身，放在 ```bash 代码块中，不要任何解释
- 命令必须兼容 Ubuntu/Debian
- 优先使用 apt（而非 apt-get）作为包管理器
- 默认不需要 sudo，如有需要可以添加
- 如果描述不清楚，生成最可能的命令，不要反问
- 一次性命令用 && 连接，多步骤操作用 && 连接相关步骤
- 如果用户的请求指代了之前的操作（如"启动它"），请根据会话历史中的上下文推断"它"指代什么"""


def translate(
    nl: str,
    *,
    session: Session | None = None,
    config: Config | None = None,
) -> str:
    """Translate natural language *nl* into a shell command.

    Parameters
    ----------
    nl:
        Natural language description of the desired command.
    session:
        Optional session cache for contextual continuity.
    config:
        Optional Config instance for API key / model preferences.

    Returns
    -------
    The generated shell command string (with markdown fences stripped).

    Raises
    ------
    RuntimeError
        When no API key is configured.
    """
    cfg = config or Config()
    api_key = cfg.api_key
    if not api_key:
        raise RuntimeError(
            "未配置 API Key。请设置 ANTHROPIC_API_KEY 环境变量，"
            "或运行 nsh config set api_key <your-key>"
        )

    base_url = cfg.get("base_url", "https://api.deepseek.com/anthropic")
    model = cfg.get("model", "claude-sonnet-4-6")
    max_tokens = cfg.get("max_tokens", 500)

    # Build system prompt with optional session context
    system_prompt = _SYSTEM_PROMPT
    if session:
        ctx = session.get_context()
        if ctx:
            system_prompt += f"\n\n{ctx}"

    client = Anthropic(api_key=api_key, base_url=base_url)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": nl}],
    )

    # Extract text from TextBlock(s), skipping ThinkingBlock etc.
    text_blocks = [b.text for b in response.content if isinstance(b, TextBlock)]
    if not text_blocks:
        raise RuntimeError("API 返回了空的响应内容，请重试。")
    raw = "".join(text_blocks)
    from nsh.executor import sanitize_command
    return sanitize_command(raw)
