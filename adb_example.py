"""
ADB 坐标自动化使用示例
演示如何使用 ADB 坐标方式进行自动化操作
"""
from adb_automation import ADBAutomation, KeyCode
import time


def example_basic_operations():
    """示例1：基本操作"""
    print("\n" + "=" * 50)
    print("示例1：基本操作")
    print("=" * 50)
    
    # 创建自动化实例（自动检测真机）
    auto = ADBAutomation()
    
    if not auto.connect():
        print("设备连接失败")
        return
    
    try:
        # 截图
        auto.take_screenshot('screen1.png')
        time.sleep(1)
        
        # 点击坐标 (500, 1000)
        auto.tap(500, 1000)
        time.sleep(1)
        
        # 再次截图
        auto.take_screenshot('screen2.png')
        
        # 返回键
        auto.back()
        
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"错误: {e}")


def example_damai_app():
    """示例2：操作大麦应用"""
    print("\n" + "=" * 50)
    print("示例2：操作大麦应用")
    print("=" * 50)
    
    auto = ADBAutomation()
    
    if not auto.connect():
        return
    
    try:
        # 启动大麦应用
        auto.launch_app('com.damai.wireless')
        time.sleep(3)  # 等待应用启动
        
        # 截图首页
        auto.take_screenshot('damai_home.png')
        
        # 获取屏幕尺寸
        width, height = auto.get_screen_size()
        print(f"屏幕尺寸: {width} x {height}")
        
        # 根据屏幕尺寸计算坐标（示例：点击底部导航栏的"我的"）
        # 注意：这些坐标需要根据实际屏幕调整
        if width == 1080 and height == 2340:
            # 示例坐标（需要根据实际情况调整）
            my_tab_x = 900  # "我的"标签的 X 坐标
            my_tab_y = 2200  # "我的"标签的 Y 坐标
            
            # 点击"我的"
            auto.tap(my_tab_x, my_tab_y)
            time.sleep(2)
            auto.take_screenshot('damai_my.png')
            
            # 返回首页
            auto.back()
            time.sleep(1)
        
        print("操作完成")
        
    except Exception as e:
        print(f"错误: {e}")


def example_swipe_and_scroll():
    """示例3：滑动和滚动"""
    print("\n" + "=" * 50)
    print("示例3：滑动和滚动")
    print("=" * 50)
    
    auto = ADBAutomation()
    
    if not auto.connect():
        return
    
    try:
        width, height = auto.get_screen_size()
        center_x = width // 2
        center_y = height // 2
        
        # 向下滑动（向上滚动）
        auto.swipe(center_x, center_y + 200, center_x, center_y - 200, duration=500)
        time.sleep(1)
        
        # 向上滑动（向下滚动）
        auto.swipe(center_x, center_y - 200, center_x, center_y + 200, duration=500)
        time.sleep(1)
        
        # 向左滑动
        auto.swipe(center_x + 200, center_y, center_x - 200, center_y, duration=500)
        time.sleep(1)
        
        # 向右滑动
        auto.swipe(center_x - 200, center_y, center_x + 200, center_y, duration=500)
        
    except Exception as e:
        print(f"错误: {e}")


def example_get_coordinates():
    """示例4：获取元素坐标"""
    print("\n" + "=" * 50)
    print("示例4：获取元素坐标")
    print("=" * 50)
    
    auto = ADBAutomation()
    
    if not auto.connect():
        return
    
    try:
        # 方法1：获取 UI 层次结构，然后手动查找坐标
        print("正在获取 UI 层次结构...")
        auto.get_ui_hierarchy('ui_hierarchy.xml')
        print("已保存到 ui_hierarchy.xml")
        print("打开文件查找元素的 bounds 属性，格式: bounds=\"[x1,y1][x2,y2]\"")
        print("元素中心点坐标 = ((x1+x2)/2, (y1+y2)/2)")
        
        # 方法2：截图后手动查看坐标
        auto.take_screenshot('for_coordinates.png')
        print("已截图保存到 for_coordinates.png")
        print("打开图片，使用图片查看器查看元素位置的坐标")
        
    except Exception as e:
        print(f"错误: {e}")


def example_custom_workflow():
    """示例5：自定义工作流程"""
    print("\n" + "=" * 50)
    print("示例5：自定义工作流程")
    print("=" * 50)
    
    auto = ADBAutomation()
    
    if not auto.connect():
        return
    
    try:
        # 启动大麦应用
        auto.launch_app('com.damai.wireless')
        time.sleep(3)
        
        # 截图步骤1
        auto.take_screenshot('step1_launch.png')
        
        # 等待页面加载
        auto.wait(2)
        
        # 执行一系列操作（需要根据实际坐标调整）
        width, height = auto.get_screen_size()
        
        # 示例：点击搜索框（需要根据实际位置调整）
        # search_x = width // 2
        # search_y = 200
        # auto.tap(search_x, search_y)
        # auto.wait(1)
        
        # 截图步骤2
        auto.take_screenshot('step2_after_action.png')
        
        print("工作流程完成")
        
    except Exception as e:
        print(f"错误: {e}")


def example_coordinate_config():
    """示例6：使用配置文件管理坐标"""
    print("\n" + "=" * 50)
    print("示例6：使用配置文件管理坐标")
    print("=" * 50)
    
    # 坐标配置示例（需要根据实际设备调整）
    # 建议将坐标保存到 JSON 或 YAML 文件中
    
    coordinates = {
        'screen_size': {
            'width': 1080,
            'height': 2340
        },
        'damai_app': {
            'home_tab': {'x': 270, 'y': 2200},
            'show_tab': {'x': 540, 'y': 2200},
            'my_tab': {'x': 900, 'y': 2200},
            'search_box': {'x': 540, 'y': 200}
        }
    }
    
    auto = ADBAutomation()
    
    if not auto.connect():
        return
    
    try:
        # 检查屏幕尺寸是否匹配
        width, height = auto.get_screen_size()
        if width != coordinates['screen_size']['width'] or height != coordinates['screen_size']['height']:
            print(f"⚠️  屏幕尺寸不匹配！")
            print(f"   配置: {coordinates['screen_size']['width']}x{coordinates['screen_size']['height']}")
            print(f"   实际: {width}x{height}")
            print("   需要重新配置坐标")
            return
        
        # 启动应用
        auto.launch_app('com.damai.wireless')
        time.sleep(3)
        
        # 使用配置的坐标点击
        my_tab = coordinates['damai_app']['my_tab']
        auto.tap(my_tab['x'], my_tab['y'])
        time.sleep(2)
        
        print("使用配置坐标操作完成")
        
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    print("ADB 坐标自动化示例")
    print("=" * 50)
    print("请选择示例：")
    print("1. 基本操作（点击、截图、返回）")
    print("2. 操作大麦应用")
    print("3. 滑动和滚动")
    print("4. 获取元素坐标")
    print("5. 自定义工作流程")
    print("6. 使用配置文件管理坐标")
    
    choice = input("\n请输入数字 (1-6): ").strip()
    
    examples = {
        '1': example_basic_operations,
        '2': example_damai_app,
        '3': example_swipe_and_scroll,
        '4': example_get_coordinates,
        '5': example_custom_workflow,
        '6': example_coordinate_config,
    }
    
    if choice in examples:
        examples[choice]()
    else:
        print("无效选择，运行基本操作示例...")
        example_basic_operations()
