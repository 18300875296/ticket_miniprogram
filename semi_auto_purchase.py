"""
纯人工触发抢票脚本（无并发 / 无自动循环）

使用说明：
- 按 '1'：点击 按钮1（详情页「确定」）
- 按 '2'：点击 按钮2（支付页「确认信息并支付」）
- 按 '3'：点击 按钮3（弹框「确认无误」）
- 按 'q'：退出程序
"""

from adb_automation import ADBAutomation
import time
import random
import msvcrt  # Windows 专用
import platform

# ================== 坐标配置 ==================
DETAIL_BOTTOM_X = 540
DETAIL_BOTTOM_Y = 1945

PAY_BUTTON_X = 850
PAY_BUTTON_Y = 2055

POPUP_CONFIRM_X = 520
POPUP_CONFIRM_Y = 1390

BUTTONS = {
    '1': {'name': '详情页「确定」', 'x': DETAIL_BOTTOM_X, 'y': DETAIL_BOTTOM_Y},
    '2': {'name': '支付页「确认信息并支付」', 'x': PAY_BUTTON_X, 'y': PAY_BUTTON_Y},
    '3': {'name': '弹框「确认无误」', 'x': POPUP_CONFIRM_X, 'y': POPUP_CONFIRM_Y},
}

# ================== 点击参数 ==================
CLICK_COORD_OFFSET = 5   # 坐标随机偏移（像素）
CLICK_COOLDOWN = 0.15    # 每次点击后的最小冷却时间（秒）

# ================== 主类 ==================
class ManualPurchase:
    def __init__(self, auto: ADBAutomation):
        self.auto = auto
        self.running = True

        # 只获取一次屏幕尺寸（重要）
        print("📱 获取屏幕尺寸中...")
        self.screen_width, self.screen_height = self.auto.get_screen_size()
        print(f"✅ 屏幕尺寸: {self.screen_width} x {self.screen_height}")

        # 简单统计
        self.stats = {
            '1': 0,
            '2': 0,
            '3': 0,
        }

    def tap_button(self, key: str):
        """点击指定按钮一次"""
        button = BUTTONS[key]

        offset_x = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
        offset_y = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)

        x = button['x'] + offset_x
        y = button['y'] + offset_y

        # 边界保护
        x = max(0, min(self.screen_width - 1, x))
        y = max(0, min(self.screen_height - 1, y))

        success = self.auto.tap(x, y)
        if success:
            self.stats[key] += 1
            print(f"🖱️ 点击 {button['name']} @ ({x},{y}) | 次数={self.stats[key]}")
        else:
            print(f"❌ 点击失败: {button['name']}")

        time.sleep(CLICK_COOLDOWN)

    def run(self):
        print("\n" + "=" * 60)
        print("🚀 纯人工触发抢票模式（无并发 / 无自动）")
        print("=" * 60)
        print("操作说明：")
        print("  1 → 详情页「确定」")
        print("  2 → 支付页「确认信息并支付」")
        print("  3 → 弹框「确认无误」")
        print("  q → 退出")
        print("=" * 60 + "\n")

        while self.running:
            if msvcrt.kbhit():
                key = msvcrt.getwch()

                # 过滤功能键前缀
                if key in ('\x00', '\xe0'):
                    continue

                if key == 'q':
                    print("\n⚠️ 用户退出")
                    self.running = False
                    break

                if key in BUTTONS:
                    self.tap_button(key)
                else:
                    if key.isprintable():
                        print(f"⚠️ 未定义按键: {repr(key)}")

            time.sleep(0.01)

        # 最终统计
        print("\n" + "=" * 60)
        print("📊 最终统计")
        print("=" * 60)
        for k, v in self.stats.items():
            print(f"按钮{k} 点击次数: {v}")
        print("=" * 60)


# ================== 入口 ==================
def main():
    if platform.system() != 'Windows':
        print("❌ 仅支持 Windows（需要 msvcrt）")
        return

    auto = ADBAutomation()
    if not auto.connect():
        print("❌ 设备连接失败")
        return

    ManualPurchase(auto).run()


if __name__ == "__main__":
    main()
