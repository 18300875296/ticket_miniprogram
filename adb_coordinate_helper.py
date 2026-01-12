"""
ADB 坐标辅助工具
帮助获取和管理坐标配置
"""
import json
import os
from adb_automation import ADBAutomation
from typing import Dict, Optional, Tuple


class CoordinateHelper:
    """坐标配置辅助类"""
    
    def __init__(self, config_file: str = 'coordinate_config.json'):
        """
        初始化坐标助手
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return self._default_config()
        else:
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "screen_sizes": {},
            "instructions": {
                "how_to_get_coordinates": [
                    "1. 运行脚本获取 UI 层次结构",
                    "2. 打开生成的 ui.xml 文件",
                    "3. 查找目标元素的 bounds 属性",
                    "4. 计算中心点坐标"
                ]
            }
        }
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"✅ 配置已保存到: {self.config_file}")
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
    
    def get_screen_key(self, width: int, height: int) -> str:
        """获取屏幕尺寸键"""
        return f"{width}x{height}"
    
    def add_screen_size(self, width: int, height: int, description: str = ""):
        """添加屏幕尺寸配置"""
        key = self.get_screen_key(width, height)
        if key not in self.config['screen_sizes']:
            self.config['screen_sizes'][key] = {
                "width": width,
                "height": height,
                "description": description,
                "coordinates": {}
            }
            print(f"✅ 已添加屏幕尺寸: {key}")
        else:
            print(f"⚠️  屏幕尺寸 {key} 已存在")
    
    def add_coordinate(self, screen_key: str, name: str, x: int, y: int, description: str = ""):
        """添加坐标"""
        if screen_key not in self.config['screen_sizes']:
            print(f"❌ 屏幕尺寸 {screen_key} 不存在，请先添加")
            return False
        
        if 'coordinates' not in self.config['screen_sizes'][screen_key]:
            self.config['screen_sizes'][screen_key]['coordinates'] = {}
        
        self.config['screen_sizes'][screen_key]['coordinates'][name] = {
            "x": x,
            "y": y,
            "description": description
        }
        print(f"✅ 已添加坐标: {name} -> ({x}, {y})")
        return True
    
    def get_coordinate(self, screen_key: str, name: str) -> Optional[Tuple[int, int]]:
        """获取坐标"""
        if screen_key not in self.config['screen_sizes']:
            return None
        
        coords = self.config['screen_sizes'][screen_key].get('coordinates', {})
        if name not in coords:
            return None
        
        coord = coords[name]
        return (coord['x'], coord['y'])
    
    def get_current_screen_coordinates(self, auto: ADBAutomation) -> Dict:
        """获取当前屏幕的坐标配置"""
        width, height = auto.get_screen_size()
        screen_key = self.get_screen_key(width, height)
        
        if screen_key in self.config['screen_sizes']:
            return self.config['screen_sizes'][screen_key].get('coordinates', {})
        else:
            print(f"⚠️  当前屏幕尺寸 {screen_key} 未配置")
            return {}


def interactive_coordinate_setup():
    """交互式坐标设置工具"""
    print("=" * 50)
    print("ADB 坐标配置工具")
    print("=" * 50)
    
    auto = ADBAutomation()
    if not auto.connect():
        return
    
    helper = CoordinateHelper()
    
    width, height = auto.get_screen_size()
    screen_key = helper.get_screen_key(width, height)
    
    print(f"\n当前屏幕尺寸: {width} x {height} ({screen_key})")
    
    # 如果屏幕尺寸不存在，添加它
    if screen_key not in helper.config['screen_sizes']:
        desc = input("请输入屏幕描述（可选）: ").strip()
        helper.add_screen_size(width, height, desc)
    
    print("\n选择操作：")
    print("1. 获取 UI 层次结构（推荐）")
    print("2. 截图查看坐标")
    print("3. 添加坐标")
    print("4. 查看当前配置")
    print("5. 测试坐标")
    
    choice = input("\n请选择 (1-5): ").strip()
    
    if choice == '1':
        # 获取 UI 层次结构
        filename = f'ui_{screen_key}.xml'
        auto.get_ui_hierarchy(filename)
        print(f"\n✅ UI 层次结构已保存到: {filename}")
        print("打开文件查找元素的 bounds 属性")
        print("格式: bounds=\"[x1,y1][x2,y2]\"")
        print("中心点: x = (x1+x2)/2, y = (y1+y2)/2")
    
    elif choice == '2':
        # 截图
        filename = f'screen_{screen_key}.png'
        auto.take_screenshot(filename)
        print(f"\n✅ 截图已保存到: {filename}")
        print("打开图片，使用图片查看器查看元素位置的坐标")
    
    elif choice == '3':
        # 添加坐标
        name = input("坐标名称: ").strip()
        x = int(input("X 坐标: ").strip())
        y = int(input("Y 坐标: ").strip())
        desc = input("描述（可选）: ").strip()
        
        helper.add_coordinate(screen_key, name, x, y, desc)
        helper.save_config()
    
    elif choice == '4':
        # 查看配置
        coords = helper.get_current_screen_coordinates(auto)
        if coords:
            print("\n当前屏幕的坐标配置：")
            for name, coord in coords.items():
                print(f"  {name}: ({coord['x']}, {coord['y']}) - {coord.get('description', '')}")
        else:
            print("\n当前屏幕暂无坐标配置")
    
    elif choice == '5':
        # 测试坐标
        coords = helper.get_current_screen_coordinates(auto)
        if not coords:
            print("当前屏幕暂无坐标配置")
            return
        
        print("\n可用坐标：")
        for i, name in enumerate(coords.keys(), 1):
            print(f"  {i}. {name}")
        
        name = input("\n输入坐标名称进行测试: ").strip()
        coord = helper.get_coordinate(screen_key, name)
        
        if coord:
            x, y = coord
            print(f"测试坐标: ({x}, {y})")
            confirm = input("确认点击？(y/n): ").strip().lower()
            if confirm == 'y':
                auto.tap(x, y)
                print("点击完成")
        else:
            print("坐标不存在")


if __name__ == "__main__":
    interactive_coordinate_setup()
