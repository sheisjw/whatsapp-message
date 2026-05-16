#!/usr/bin/env python3

"""
WhatsApp 定时提醒调度器

原理：由 cron 每天早上触发一次，脚本读取 reminders.yaml，
      判断今天是否需要发哪些提醒，调用 whatsapp-mcp 发送消息。

依赖：
  pip install pyyaml requests

运行方式（手动测试）：
  python3 scheduler.py

运行方式（cron 每天 9:00 自动触发）：
  crontab -e
  0 9 * * * /usr/bin/python3 /path/to/scheduler.py >> /path/to/scheduler.log 2>&1
"""

import re
import sys
from datetime import datetime, date
import calendar
from pathlib import Path

import yaml
import requests

# ─── 配置 ─────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "reminders.yaml"
LOG_FILE    = Path(__file__).parent / "scheduler.log"
MCP_URL     = "http://localhost:8081/mcp/0501b6354bea8a78f802b58cec76bcfc"
DRY_RUN     = False  # True = 只打印不发送，用于测试
# ──────────────────────────────────────────────────────


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config() -> list[dict]:
    if not CONFIG_FILE.exists():
        log(f"❌ 找不到配置文件：{CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("reminders", [])


def should_trigger_today(schedule: dict, today: date) -> bool:
    if "day" in schedule:
        day_val = schedule["day"]
        if day_val == "last":
            last_day = calendar.monthrange(today.year, today.month)[1]
            return today.day == last_day
        return today.day == int(day_val)

    if "weekday" in schedule:
        weekday_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        target = weekday_map.get(schedule["weekday"].lower())
        return today.weekday() == target

    return False


def init_mcp_session() -> str | None:
    try:
        resp = requests.post(MCP_URL, json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "scheduler", "version": "1.0"},
            },
            "id": 0,
        }, timeout=10)
        return resp.headers.get("mcp-session-id")
    except Exception as e:
        log(f"❌ MCP 初始化失败：{e}")
        return None


def call_tool(session_id: str, tool_name: str, arguments: dict) -> str | None:
    """调用 MCP 工具，返回纯文本结果，失败返回 None。"""
    try:
        resp = requests.post(MCP_URL, json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1,
        }, headers={"mcp-session-id": session_id}, timeout=15)
        body = resp.json()
        result = body.get("result", {})
        if result.get("isError"):
            content = result.get("content", [{}])
            log(f"  ❌ 工具错误：{content[0].get('text', '未知错误')}")
            return None
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return content[0]["text"]
        return None
    except Exception as e:
        log(f"  ❌ 工具调用异常：{e}")
        return None


def resolve_contact(session_id: str, contact: str) -> str | None:
    contact = str(contact)
    # 手机号直接转 JID
    if contact.startswith("+"):
        digits = re.sub(r"[\s\-\+]", "", contact)
        return f"{digits}@s.whatsapp.net"

    text = call_tool(session_id, "find_chat", {"search": contact})
    if not text:
        log(f"  ⚠️  找不到联系人：{contact}")
        return None

    # 从返回文本里提取第一个 JID，格式：   JID: xxxxx@s.whatsapp.net
    match = re.search(r"JID:\s*(\S+@\S+)", text)
    if match:
        return match.group(1)

    log(f"  ⚠️  找不到联系人：{contact}")
    return None


def send_whatsapp_message(session_id: str, chat_jid: str, message: str) -> bool:
    if DRY_RUN:
        log(f"  [DRY RUN] 将发送给 {chat_jid}：{message[:50]}...")
        return True

    text = call_tool(session_id, "send_message", {"chat_jid": chat_jid, "text": message})
    return text is not None


def format_message(template: str, today: date) -> str:
    return template.strip().format(year=today.year, month=today.month, day=today.day)


def run():
    today = date.today()
    log(f"🚀 调度器启动，今天是 {today.strftime('%Y-%m-%d')}（{'周' + '一二三四五六日'[today.weekday()]}）")

    session_id = init_mcp_session()
    if not session_id:
        log("❌ 无法建立 MCP 会话，退出")
        sys.exit(1)
    log(f"✅ MCP 会话建立：{session_id[:8]}...")

    reminders = load_config()
    triggered = 0

    for task in reminders:
        name     = task.get("name", "未命名任务")
        contact  = task.get("contact", "")
        message  = task.get("message", "")
        schedule = task.get("schedule", {})

        if not should_trigger_today(schedule, today):
            continue

        log(f"📬 触发任务：{name} → {contact}")

        chat_jid = resolve_contact(session_id, contact)
        if not chat_jid:
            continue

        msg = format_message(message, today)
        success = send_whatsapp_message(session_id, chat_jid, msg)

        if success:
            log(f"  ✅ 发送成功")
            triggered += 1
        else:
            log(f"  ❌ 发送失败")

    if triggered == 0:
        log("📭 今天没有需要触发的提醒")
    else:
        log(f"✅ 今天共发送 {triggered} 条提醒")


if __name__ == "__main__":
    run()
