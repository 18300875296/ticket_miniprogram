"""
半自动抢票脚本（人工+自动）
用户观察屏幕，看到页面更新后按键盘触发下一阶段

线程架构：
1. 线程1：监听键盘输入（使用 msvcrt）
2. 线程2：根据当前阶段循环点击对应按钮

使用说明：
- 按空格键：进入下一阶段
- 按 '1'：切换到阶段1（按钮1）
- 按 '2'：切换到阶段2（按钮2）
- 按 '3'：切换到阶段3（按钮3）
- 按 'q'：退出程序
"""
from adb_automation import ADBAutomation
import time
import threading
import random
import msvcrt  # Windows 专用

# 坐标配置
DETAIL_BOTTOM_X = 520
DETAIL_BOTTOM_Y = 1965
PAY_BUTTON_X = 850
PAY_BUTTON_Y = 2050
POPUP_CONFIRM_X = 520
POPUP_CONFIRM_Y = 1390

# 按钮配置
BUTTONS = [
    {'name': '详情页「确定」', 'x': DETAIL_BOTTOM_X, 'y': DETAIL_BOTTOM_Y},
    {'name': '支付页「确认信息并支付」', 'x': PAY_BUTTON_X, 'y': PAY_BUTTON_Y},
    {'name': '弹框「确认无误」', 'x': POPUP_CONFIRM_X, 'y': POPUP_CONFIRM_Y},
]

# 点击配置
CLICK_INTERVAL_MIN = 0.15   # 最小点击间隔（秒）
CLICK_INTERVAL_MAX = 0.25   # 最大点击间隔（秒）
CLICK_COORD_OFFSET = 5       # 坐标随机偏移范围（像素）


class SemiAutoPurchase:
    """半自动抢票类（人工+自动）"""
    
    def __init__(self, auto: ADBAutomation):
        self.auto = auto
        
        # 当前阶段（0=按钮1, 1=按钮2, 2=按钮3）
        self.current_stage = 0
        self.stage_lock = threading.Lock()
        
        # 控制标志
        self.running = threading.Event()
        self.running.set()
        
        # 统计信息
        self.stats = {
            'button1_clicks': 0,
            'button2_clicks': 0,
            'button3_clicks': 0,
        }
        self.stats_lock = threading.Lock()
    
    def get_stage(self) -> int:
        """获取当前阶段（线程安全）"""
        with self.stage_lock:
            return self.current_stage
    
    def set_stage(self, stage: int):
        """设置当前阶段（线程安全）"""
        with self.stage_lock:
            if 0 <= stage < len(BUTTONS):
                self.current_stage = stage
                print(f"\n✅ 切换到阶段 {stage + 1}: {BUTTONS[stage]['name']}")
            else:
                print(f"⚠️ 无效的阶段: {stage}")
    
    def next_stage(self):
        """进入下一阶段"""
        current = self.get_stage()
        if current < len(BUTTONS) - 1:
            self.set_stage(current + 1)
        else:
            print("⚠️ 已经是最后阶段，无法继续")
    
    def update_stats(self, key: str, value: int = 1):
        """更新统计信息（线程安全）"""
        with self.stats_lock:
            if key in self.stats:
                self.stats[key] += value
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.stats_lock:
            return self.stats.copy()
    
    def thread_keyboard_listener(self):
        """线程1：监听键盘输入"""
        print("⌨️  键盘监听线程启动")
        print("\n操作说明：")
        print("  - 空格键：进入下一阶段")
        print("  - '1'：切换到阶段1（详情页「确定」）")
        print("  - '2'：切换到阶段2（支付页「确认信息并支付」）")
        print("  - '3'：切换到阶段3（弹框「确认无误」）")
        print("  - 'q'：退出程序")
        print("\n等待键盘输入...\n")
        
        while self.running.is_set():
            try:
                # 非阻塞读取键盘输入
                if msvcrt.kbhit():
                    # 使用 getwch() 更安全，直接返回 Unicode 字符（与项目其他文件一致）
                    key = msvcrt.getwch().lower()
                    
                    if key == ' ':  # 空格键：下一阶段
                        self.next_stage()
                    elif key == '1':
                        self.set_stage(0)
                    elif key == '2':
                        self.set_stage(1)
                    elif key == '3':
                        self.set_stage(2)
                    elif key == 'q':
                        print("\n⚠️ 用户退出，正在停止...")
                        self.running.clear()
                        break
                    else:
                        print(f"⚠️ 未知按键: {key}，按 'q' 退出")
                
                time.sleep(0.05)  # 避免CPU占用过高
            except Exception as e:
                print(f"❌ 键盘监听错误: {e}")
                time.sleep(0.1)
    
    def thread_click_loop(self):
        """线程2：根据当前阶段循环点击对应按钮"""
        print("🖱️  点击线程启动")
        
        while self.running.is_set():
            try:
                stage = self.get_stage()
                button = BUTTONS[stage]
                
                # 添加随机坐标偏移
                offset_x = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
                offset_y = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
                x = button['x'] + offset_x
                y = button['y'] + offset_y
                
                # 边界检查（可选，如果需要的话）
                # screen_width, screen_height = self.auto.get_screen_size()
                # x = max(0, min(screen_width - 1, x))
                # y = max(0, min(screen_height - 1, y))
                
                # 执行点击
                success, _ = self.auto._run_adb_command(['shell', 'input', 'tap', str(x), str(y)])
                
                if success:
                    # 更新统计
                    stats_key = f'button{stage + 1}_clicks'
                    self.update_stats(stats_key)
                
                # 随机延迟，模拟人类点击
                delay = random.uniform(CLICK_INTERVAL_MIN, CLICK_INTERVAL_MAX)
                time.sleep(delay)
                
            except Exception as e:
                print(f"❌ 点击线程错误: {e}")
                time.sleep(0.1)
    
    def run(self):
        """运行半自动抢票流程"""
        print("\n" + "=" * 60)
        print("🚀 半自动抢票模式启动（人工+自动）")
        print("=" * 60)
        print(f"📌 按钮1坐标: ({BUTTONS[0]['x']}, {BUTTONS[0]['y']}) - {BUTTONS[0]['name']}")
        print(f"📌 按钮2坐标: ({BUTTONS[1]['x']}, {BUTTONS[1]['y']}) - {BUTTONS[1]['name']}")
        print(f"📌 按钮3坐标: ({BUTTONS[2]['x']}, {BUTTONS[2]['y']}) - {BUTTONS[2]['name']}")
        print("=" * 60)
        print(f"\n当前阶段: 阶段1 - {BUTTONS[0]['name']}")
        print("开始自动点击，观察屏幕变化，按空格键进入下一阶段\n")
        
        # 创建并启动线程
        keyboard_thread = threading.Thread(target=self.thread_keyboard_listener, daemon=True)
        click_thread = threading.Thread(target=self.thread_click_loop, daemon=True)
        
        keyboard_thread.start()
        click_thread.start()
        
        print("✅ 所有线程已启动")
        print("=" * 60 + "\n")
        
        try:
            # 主线程等待
            counter = 0
            while self.running.is_set():
                time.sleep(1)
                counter += 1
                
                # 每5秒打印一次统计
                if counter % 5 == 0:
                    stats = self.get_stats()
                    stage = self.get_stage()
                    print(f"📊 [阶段{stage + 1}] 按钮1={stats['button1_clicks']}, "
                          f"按钮2={stats['button2_clicks']}, "
                          f"按钮3={stats['button3_clicks']}")
                
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断，正在停止...")
            self.running.clear()
        
        # 等待线程结束
        keyboard_thread.join(timeout=1.0)
        click_thread.join(timeout=1.0)
        
        # 打印最终统计
        stats = self.get_stats()
        print("\n" + "=" * 60)
        print("📊 最终统计")
        print("=" * 60)
        print(f"🖱️  按钮1点击次数: {stats['button1_clicks']}")
        print(f"🖱️  按钮2点击次数: {stats['button2_clicks']}")
        print(f"🖱️  按钮3点击次数: {stats['button3_clicks']}")
        print("=" * 60)


def main():
    """主函数"""
    # 检查是否在Windows系统
    import platform
    if platform.system() != 'Windows':
        print("❌ 此脚本仅支持 Windows 系统（需要 msvcrt 模块）")
        return
    
    auto = ADBAutomation()
    
    if not auto.connect():
        print("❌ 设备连接失败")
        return
    
    purchase = SemiAutoPurchase(auto)
    purchase.run()


if __name__ == "__main__":
    main()

