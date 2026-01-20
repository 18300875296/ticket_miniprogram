# 🎫 快速抢购工具

基于 ADB 的 Android 手机自动化抢购工具，支持高频点击和自动刷新。

---

## 📚 文档导航

### 🆕 新手入门
- **[使用说明.md](./使用说明.md)** - 完整详细的使用指南（推荐新手）
  - 环境配置（Python、ADB）
  - 手机设置（USB调试）
  - 详细使用步骤
  - 常见问题解答

### ⚡ 快速上手
- **[快速开始.md](./快速开始.md)** - 5分钟快速上手（有经验用户）

---

## 🚀 功能特性

- ✅ **高频点击**：多线程并发，最高可达 200+ 次/秒
- ✅ **自动刷新**：可配置自动下拉刷新页面
- ✅ **实时统计**：显示点击次数和速度
- ✅ **简单易用**：交互式配置，无需编程基础
- ✅ **安全可靠**：线程安全，可随时停止

---

## 📋 文件说明

| 文件 | 说明 |
|------|------|
| `adb_automation.py` | 核心自动化类库 |
| `fast_click_snatch.py` | 快速抢购脚本（主程序） |
| `quick_start_adb.py` | 快速开始测试脚本 |
| `adb_coordinate_helper.py` | 坐标获取辅助工具 |
| `adb_example.py` | 更多使用示例 |
| `使用说明.md` | 详细使用文档 |
| `快速开始.md` | 快速上手指南 |

---

## ⚙️ 系统要求

- **操作系统**：Windows 10/11
- **Python**：3.8 或更高版本
- **ADB**：Android SDK Platform Tools
- **手机**：Android 5.0 或更高版本

---

## 🎯 快速开始

### 1. 环境准备
```bash
# 检查 Python
python --version

# 检查 ADB
adb version

# 检查设备连接
adb devices
```

### 2. 运行脚本
```bash
python fast_click_snatch.py
```

### 3. 按提示输入参数
- 按钮坐标（必须）
- 线程数量（可选，默认5）
- 刷新间隔（可选，默认10）

---

## 📖 使用示例

### 基本使用
```python
from adb_automation import ADBAutomation, FastClicker

# 连接设备
auto = ADBAutomation()
auto.connect()

# 创建快速点击器
clicker = FastClicker(
    automation=auto,
    button_x=540,
    button_y=1600
)

# 启动抢购
clicker.start(
    thread_count=5,
    refresh_interval=10
)
```

### 获取坐标
```python
from adb_automation import ADBAutomation

auto = ADBAutomation()
auto.connect()

# 截图
auto.take_screenshot('screenshot.png')

# 获取 UI 层次结构
auto.get_ui_hierarchy('ui.xml')
```

---

## ❓ 常见问题

**Q: 设备连接失败？**  
A: 检查 USB 连接、USB 调试是否开启、是否授权。详见 [使用说明.md](./使用说明.md)

**Q: 如何获取按钮坐标？**  
A: 使用 `python adb_coordinate_helper.py` 或 `python quick_start_adb.py` 截图

**Q: 点击速度慢？**  
A: 增加线程数量（建议不超过8），减小延迟范围

**Q: 如何停止？**  
A: 按 `Ctrl + C`

更多问题请查看 [使用说明.md](./使用说明.md) 的常见问题部分。

---

## 📝 注意事项

- ⚠️ 请合理使用，不要设置过高的线程数
- ⚠️ 建议延迟不要小于 0.01 秒
- ⚠️ 长时间运行可能对手机造成负担
- ⚠️ 仅用于学习和个人使用

---

## 📞 获取帮助

遇到问题？
1. 查看 [使用说明.md](./使用说明.md) 的常见问题部分
2. 检查错误信息
3. 联系开发者

---

## 📄 许可证

本项目仅供学习交流使用。

---

**祝抢购成功！🎉**

