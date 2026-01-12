"""
ADB 坐标自动化快速开始脚本
最简单的使用示例
"""
from adb_automation import ADBAutomation
import time


def main():
    """快速开始示例"""
    print("=" * 50)
    print("ADB 坐标自动化 - 快速开始")
    print("=" * 50)
    
    # 创建自动化实例
    auto = ADBAutomation()
    
    # 连接设备
    if not auto.connect():
        print("\n❌ 设备连接失败，请检查：")
        print("1. 手机是否通过 USB 连接")
        print("2. 是否启用 USB 调试")
        print("3. 是否授权 USB 调试")
        return
    
    print("\n✅ 设备连接成功！")
    print("\n提示：")
    print("- 使用 auto.tap(x, y) 点击坐标")
    print("- 使用 auto.take_screenshot() 截图")
    print("- 使用 auto.get_ui_hierarchy() 获取 UI 层次结构")
    print("- 运行 python adb_example.py 查看更多示例")
    
    try:
        # 示例：截图
        print("\n正在截图...")
        auto.take_screenshot('quick_start_screenshot.png')
        
        # 获取屏幕尺寸
        width, height = auto.get_screen_size()
        print(f"\n屏幕尺寸: {width} x {height}")
        
        # 提示如何获取坐标
        print("\n如何获取坐标：")
        print("1. 运行: auto.get_ui_hierarchy('ui.xml')")
        print("2. 打开 ui.xml 文件查找元素的 bounds 属性")
        print("3. 或截图后使用图片查看器查看坐标")
        
        # 等待用户操作
        print("\n" + "=" * 50)
        print("保持连接中，可以继续操作...")
        print("按 Ctrl+C 退出")
        print("=" * 50)
        
        # 保持连接
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n用户中断，退出")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
