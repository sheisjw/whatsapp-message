# WhatsApp 定时提醒系统

每天自动检查是否需要给某人发 WhatsApp 提醒，完全跑在本地，不依赖任何云服务。

---

## 文件结构

```
whatsapp_reminders/
├── reminders.yaml   ← 在这里配置所有提醒任务
├── scheduler.py     ← 调度脚本（由 cron 每天触发）
├── scheduler.log    ← 运行日志（自动生成）
└── README.md
```

---

## 第一步：安装 whatsapp-mcp

whatsapp-mcp 分两部分：Go 桥接程序 + Python MCP 服务器。

```bash
# 1. 安装 Go（如果还没有）
brew install go

# 2. 克隆项目
git clone https://github.com/lharries/whatsapp-mcp.git
cd whatsapp-mcp

# 3. 启动 Go 桥接程序（首次运行会显示二维码）
cd whatsapp-bridge
go run main.go
```

用手机 **WhatsApp** 扫描终端里的二维码，完成授权后桥接程序会常驻运行。

> 之后每次开机需要重新启动 Go 桥接程序，建议加入开机启动项（见下方）。

---

## 第二步：安装 Python 依赖

```bash
pip install pyyaml requests
```

---

## 第三步：配置提醒任务

打开 `reminders.yaml`，按格式添加你的提醒：

```yaml
reminders:

  - name: 提醒张三交月报
    contact: 张三              # 联系人名（与 WhatsApp 通讯录一致）
    message: |
      Hi，{month}月月报记得今天提交哦 📋
    schedule:
      day: 25                  # 每月 25 号触发

  - name: 提醒李四更新数据
    contact: +8613800138000    # 也可以直接填手机号
    message: 每月20号提醒：麻烦更新本月数据，谢谢！
    schedule:
      day: 20                  # 每月 20 号触发

  - name: 每周一例会提醒
    contact: 王五
    message: 周会提醒：今天下午3点 🙂
    schedule:
      weekday: monday          # 每周一触发
```

**支持的 `schedule` 格式：**

| 写法 | 含义 |
|------|------|
| `day: 20` | 每月 20 号 |
| `day: 1` | 每月 1 号 |
| `day: last` | 每月最后一天 |
| `weekday: monday` | 每周一 |
| `weekday: friday` | 每周五 |

**消息内支持的变量：**

| 变量 | 含义 |
|------|------|
| `{year}` | 当前年份，如 2026 |
| `{month}` | 当前月份，如 5 |
| `{day}` | 当前日期，如 20 |

---

## 第四步：测试运行

先开启 dry run 模式（只打印，不真正发消息），确认逻辑正确：

```bash
# 打开 scheduler.py，将第 27 行改为：
DRY_RUN = True

# 运行
python3 scheduler.py
```

确认输出正确后，改回 `DRY_RUN = False`，再测试真实发送：

```bash
python3 scheduler.py
```

---

## 第五步：设置 cron 定时触发

```bash
# 打开 crontab 编辑器
crontab -e
```

添加以下内容（每天早上 9:00 触发）：

```cron
0 9 * * * /usr/bin/python3 /完整路径/whatsapp_reminders/scheduler.py >> /完整路径/whatsapp_reminders/scheduler.log 2>&1
```

> 注意替换为你的实际路径，用 `which python3` 确认 python3 的完整路径。

查看 cron 是否生效：

```bash
crontab -l
```

---

## 设置桥接程序开机自启（可选）

```bash
# 创建 launchd plist
cat > ~/Library/LaunchAgents/com.whatsapp.bridge.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.whatsapp.bridge</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/go/bin/go</string>
    <string>run</string>
    <string>main.go</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/你的路径/whatsapp-mcp/whatsapp-bridge</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
</dict>
</plist>
EOF

# 加载
launchctl load ~/Library/LaunchAgents/com.whatsapp.bridge.plist
```

---

## 查看运行日志

```bash
tail -f scheduler.log
```

---

## 新增提醒

只需在 `reminders.yaml` 里添加一条，下次 cron 触发时自动生效，无需重启任何服务。

---

## 常见问题

**Q：找不到联系人**
A：确认 `contact` 字段的名字与 WhatsApp 通讯录完全一致；或改用手机号格式（`+86...`）更可靠。

**Q：cron 触发了但没发消息**
A：检查 `scheduler.log`；最常见原因是 Go 桥接程序没有运行，重新启动 `go run main.go`。

**Q：想临时跳过某个提醒**
A：在 `reminders.yaml` 对应任务前加 `#` 注释掉即可。
# whatsapp-message
