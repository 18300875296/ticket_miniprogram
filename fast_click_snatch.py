"""
快速抢购脚本 - 高频点击器
用于快速抢购场景，支持多线程并发点击和自动刷新
"""
from adb_automation import ADBAutomation, FastClicker
import time


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 快速抢购工具")
    print("=" * 60)
    
    # 1. 连接设备
    auto = ADBAutomation()
    if not auto.connect():
        print("❌ 设备连接失败，请检查：")
        print("   1. 手机已通过 USB 连接到电脑")
        print("   2. 已启用 USB 调试")
        print("   3. 手机上已授权 USB 调试")
        return
    
    # 2. 获取屏幕尺寸
    width, height = auto.get_screen_size()
    print(f"\n📱 屏幕尺寸: {width} x {height}")
    
    # 3. 配置抢购参数
    print("\n" + "=" * 60)
    print("⚙️  配置抢购参数")
    print("=" * 60)
    
    try:
        # 按钮坐标
        print("\n📍 请输入抢购按钮的坐标：")
        button_x = int(input("   按钮 X 坐标: ").strip())
        button_y = int(input("   按钮 Y 坐标: ").strip())
        
        # 线程数量
        thread_count_input = input("\n🧵 线程数量 (默认 5，建议 3-8): ").strip()
        thread_count = int(thread_count_input) if thread_count_input else 5
        
        # 刷新间隔
        refresh_input = input("🔄 刷新间隔 (每 N 次点击刷新，默认 10，0=不刷新): ").strip()
        refresh_interval = int(refresh_input) if refresh_input else 10
        
        # 延迟范围
        min_delay_input = input("⏱️  最小延迟秒数 (默认 0.01): ").strip()
        min_delay = float(min_delay_input) if min_delay_input else 0.01
        
        max_delay_input = input("⏱️  最大延迟秒数 (默认 0.05): ").strip()
        max_delay = float(max_delay_input) if max_delay_input else 0.05
        
        # 确认配置
        print("\n" + "=" * 60)
        print("📋 配置确认")
        print("=" * 60)
        print(f"按钮坐标: ({button_x}, {button_y})")
        print(f"线程数量: {thread_count}")
        print(f"刷新间隔: 每 {refresh_interval} 次点击" if refresh_interval > 0 else "刷新: 关闭")
        print(f"延迟范围: {min_delay:.3f}s - {max_delay:.3f}s")
        print("=" * 60)
        
        confirm = input("\n确认开始抢购？(y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return
        
        # 4. 创建快速点击器
        clicker = FastClicker(
            automation=auto,
            button_x=button_x,
            button_y=button_y
        )
        
        # 5. 倒计时
        print("\n⏰ 3秒后开始抢购...")
        for i in range(3, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
        
        # 6. 启动高频点击
        clicker.start(
            thread_count=thread_count,
            refresh_interval=refresh_interval,
            min_delay=min_delay,
            max_delay=max_delay,
            stats_interval=1.0
        )
        
    except ValueError as e:
        print(f"❌ 输入错误: {e}")
        print("   请输入有效的数字")
    except KeyboardInterrupt:
        print("\n\n✅ 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")


def quick_start(button_x: int, button_y: int, thread_count: int = 5, refresh_interval: int = 10):
    """
    快速启动 - 使用预设参数
    
    Args:
        button_x: 按钮 X 坐标
        button_y: 按钮 Y 坐标
        thread_count: 线程数量
        refresh_interval: 刷新间隔
    """
    auto = ADBAutomation()
    if not auto.connect():
        return
    
    clicker = FastClicker(
        automation=auto,
        button_x=button_x,
        button_y=button_y
    )
    
    print(f"\n🚀 快速启动抢购")
    print(f"坐标: ({button_x}, {button_y})")
    print(f"线程: {thread_count}")
    print("3秒后开始...\n")
    time.sleep(3)
    
    clicker.start(
        thread_count=thread_count,
        refresh_interval=refresh_interval,
        min_delay=0.01,
        max_delay=0.05
    )


if __name__ == "__main__":
    # 方式1：交互式配置
    main()
    
    # 方式2：快速启动（取消注释并修改坐标）
    # quick_start(button_x=540, button_y=1600, thread_count=5, refresh_interval=10)

