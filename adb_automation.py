"""
基于 ADB 坐标的 Android 真机自动化脚本
不依赖 Appium，直接使用 ADB 命令进行点击、滑动等操作
"""
import subprocess
import time
import os
import platform
from typing import Optional, Tuple, List


class ADBAutomation:
    """基于 ADB 的 Android 自动化操作类"""
    
    def __init__(self, device_udid: Optional[str] = None, adb_path: Optional[str] = None):
        """
        初始化 ADB 自动化
        
        Args:
            device_udid: 设备 UDID（序列号），None 则自动检测第一个真机
            adb_path: ADB 可执行文件的完整路径，None 则自动检测
        """
        self.device_udid = device_udid
        self.screen_width = None
        self.screen_height = None
        self.adb_path = adb_path or self._find_adb_path()
        
        if not self.adb_path:
            print("⚠️  警告：未找到 ADB，某些功能可能无法使用")
            print("   请运行 setup_adb_path.ps1 配置 ADB 路径")
    
    def _find_adb_path(self) -> Optional[str]:
        """自动查找 ADB 可执行文件路径"""
        # 首先尝试直接使用 adb（如果已在 PATH 中）
        try:
            result = subprocess.run(
                ['adb', 'version'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return 'adb'  # 返回命令名，subprocess 会自动查找
        except:
            pass
        
        # 如果不在 PATH 中，搜索常见位置
        if platform.system() == 'Windows':
            possible_paths = [
                r'D:\zhuxuwen\platform-tools\adb.exe',  # 用户指定的路径
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local', 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
                os.path.join('C:', 'Android', 'platform-tools', 'adb.exe'),
                os.path.join('C:', 'adb', 'adb.exe'),
                os.path.join('C:', 'platform-tools', 'adb.exe'),
            ]
        else:
            # Linux/Mac
            possible_paths = [
                '/usr/bin/adb',
                '/usr/local/bin/adb',
                os.path.join(os.environ.get('HOME', ''), 'Android', 'Sdk', 'platform-tools', 'adb'),
            ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def find_real_devices(self) -> List[str]:
        """查找所有已连接的真机设备（排除模拟器）"""
        if not self.adb_path:
            print("❌ ADB 未找到，无法查找设备")
            print("   请运行 setup_adb_path.ps1 配置 ADB 路径")
            return []
        
        try:
            result = subprocess.run(
                [self.adb_path, 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳过第一行标题
            
            for line in lines:
                if 'device' in line and line.strip():
                    # 提取设备 UDID
                    udid = line.split('\t')[0].strip()
                    # 排除模拟器（127.0.0.1 开头的都是模拟器）
                    if udid and not udid.startswith('127.0.0.1'):
                        devices.append(udid)
            
            return devices
            
        except Exception as e:
            print(f"查找设备失败: {e}")
            return []
    
    def detect_device(self) -> Optional[str]:
        """自动检测第一个真机设备"""
        print("正在检测真机设备...")
        
        devices = self.find_real_devices()
        
        if not devices:
            print("❌ 未找到已连接的真机设备")
            print("\n请确保：")
            print("1. 手机已通过 USB 连接到电脑")
            print("2. 已启用 USB 调试（设置 → 开发者选项 → USB 调试）")
            print("3. 手机上已点击'允许 USB 调试'")
            return None
        
        if len(devices) > 1:
            print(f"⚠️  检测到 {len(devices)} 个真机设备，将使用第一个: {devices[0]}")
            print("   其他设备:", ", ".join(devices[1:]))
        else:
            print(f"✅ 检测到真机设备: {devices[0]}")
        
        return devices[0]
    
    def check_adb_connection(self) -> bool:
        """检查 ADB 连接"""
        devices = self.find_real_devices()
        
        if devices:
            print(f"✅ 检测到 {len(devices)} 个已连接的真机设备")
            for device in devices:
                print(f"   - {device}")
            return True
        else:
            print("❌ 未检测到已连接的真机设备")
            print("\n请确保：")
            print("1. 手机已通过 USB 连接到电脑")
            print("2. 已启用 USB 调试")
            print("3. 手机上已授权 USB 调试")
            return False
    
    def connect(self) -> bool:
        """连接设备并初始化"""
        print("=" * 50)
        print("ADB 坐标自动化工具")
        print("=" * 50)
        
        # 1. 检查 ADB 连接
        if not self.check_adb_connection():
            return False
        
        # 2. 确定设备 UDID
        if self.device_udid:
            udid = self.device_udid
            print(f"使用指定设备: {udid}")
        else:
            udid = self.detect_device()
            if not udid:
                return False
        
        self.device_udid = udid
        
        # 3. 获取屏幕尺寸
        self._get_screen_size()
        
        print(f"\n✅ 设备连接成功！")
        print(f"   设备 UDID: {self.device_udid}")
        print(f"   屏幕尺寸: {self.screen_width} x {self.screen_height}")
        
        return True
    
    def _get_screen_size(self):
        """获取屏幕尺寸"""
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.device_udid, 'shell', 'wm', 'size'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # 解析输出，格式通常是: Physical size: 1080x2340
            output = result.stdout.strip()
            if 'Physical size:' in output:
                size_str = output.split('Physical size:')[1].strip()
                width, height = map(int, size_str.split('x'))
                self.screen_width = width
                self.screen_height = height
            else:
                # 备用方法
                result = subprocess.run(
                    ['adb', '-s', self.device_udid, 'shell', 'getevent', '-p'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # 如果无法获取，使用默认值
                self.screen_width = 1080
                self.screen_height = 2340
                
        except Exception as e:
            print(f"获取屏幕尺寸失败: {e}，使用默认值")
            self.screen_width = 1080
            self.screen_height = 2340
    
    def _run_adb_command(self, command: List[str], timeout: int = 5) -> Tuple[bool, str]:
        """
        执行 ADB 命令
        
        Args:
            command: 命令列表，如 ['shell', 'input', 'tap', '100', '200']
            timeout: 超时时间（秒）
        
        Returns:
            (成功标志, 输出信息)
        """
        if not self.device_udid:
            return False, "未指定设备"
        
        if not self.adb_path:
            return False, "ADB 未找到，请运行 setup_adb_path.ps1 配置"
        
        try:
            full_command = [self.adb_path, '-s', self.device_udid] + command
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
                
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
    
    def tap(self, x: int, y: int, delay: float = 0.5) -> bool:
        """
        点击坐标
        
        Args:
            x: X 坐标
            y: Y 坐标
            delay: 点击后等待时间（秒）
        
        Returns:
            是否成功
        """
        success, msg = self._run_adb_command(['shell', 'input', 'tap', str(x), str(y)])
        
        if success:
            print(f"✅ 点击坐标: ({x}, {y})")
            time.sleep(delay)
            return True
        else:
            print(f"❌ 点击失败 ({x}, {y}): {msg}")
            return False
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300, delay: float = 0.5) -> bool:
        """
        滑动操作
        
        Args:
            x1: 起始 X 坐标
            y1: 起始 Y 坐标
            x2: 结束 X 坐标
            y2: 结束 Y 坐标
            duration: 滑动持续时间（毫秒）
            delay: 滑动后等待时间（秒）
        
        Returns:
            是否成功
        """
        success, msg = self._run_adb_command([
            'shell', 'input', 'swipe',
            str(x1), str(y1), str(x2), str(y2), str(duration)
        ])
        
        if success:
            print(f"✅ 滑动: ({x1}, {y1}) -> ({x2}, {y2}), 时长: {duration}ms")
            time.sleep(delay)
            return True
        else:
            print(f"❌ 滑动失败: {msg}")
            return False
    
    def long_press(self, x: int, y: int, duration: int = 1000, delay: float = 0.5) -> bool:
        """
        长按操作
        
        Args:
            x: X 坐标
            y: Y 坐标
            duration: 长按持续时间（毫秒）
            delay: 长按后等待时间（秒）
        
        Returns:
            是否成功
        """
        # 长按通过滑动实现：从同一点滑动到同一点
        success, msg = self._run_adb_command([
            'shell', 'input', 'swipe',
            str(x), str(y), str(x), str(y), str(duration)
        ])
        
        if success:
            print(f"✅ 长按坐标: ({x}, {y}), 时长: {duration}ms")
            time.sleep(delay)
            return True
        else:
            print(f"❌ 长按失败 ({x}, {y}): {msg}")
            return False
    
    def input_text(self, text: str, delay: float = 0.5) -> bool:
        """
        输入文本
        
        Args:
            text: 要输入的文本
            delay: 输入后等待时间（秒）
        
        Returns:
            是否成功
        """
        # 转义特殊字符
        text = text.replace(' ', '%s').replace('&', '\\&')
        success, msg = self._run_adb_command(['shell', 'input', 'text', text])
        
        if success:
            print(f"✅ 输入文本: {text}")
            time.sleep(delay)
            return True
        else:
            print(f"❌ 输入文本失败: {msg}")
            return False
    
    def key_event(self, keycode: int, delay: float = 0.5) -> bool:
        """
        按键事件
        
        Args:
            keycode: 按键码（如 4=返回键, 3=Home键, 24=音量+, 25=音量-）
            delay: 按键后等待时间（秒）
        
        Returns:
            是否成功
        """
        success, msg = self._run_adb_command(['shell', 'input', 'keyevent', str(keycode)])
        
        if success:
            print(f"✅ 按键: {keycode}")
            time.sleep(delay)
            return True
        else:
            print(f"❌ 按键失败: {msg}")
            return False
    
    def back(self) -> bool:
        """返回键"""
        return self.key_event(4)
    
    def home(self) -> bool:
        """Home 键"""
        return self.key_event(3)
    
    def menu(self) -> bool:
        """菜单键"""
        return self.key_event(82)
    
    def take_screenshot(self, filename: str = 'screenshot.png', local_path: Optional[str] = None) -> bool:
        """
        截图
        
        Args:
            filename: 截图文件名
            local_path: 本地保存路径，None 则保存到当前目录
        
        Returns:
            是否成功
        """
        if local_path is None:
            local_path = filename
        
        try:
            # 在设备上截图
            device_path = f'/sdcard/{filename}'
            success, msg = self._run_adb_command(['shell', 'screencap', '-p', device_path])
            
            if not success:
                print(f"❌ 截图失败: {msg}")
                return False
            
            # 拉取到本地
            success, msg = self._run_adb_command(['pull', device_path, local_path])
            
            if success:
                # 删除设备上的截图
                self._run_adb_command(['shell', 'rm', device_path])
                print(f"✅ 截图已保存: {local_path}")
                return True
            else:
                print(f"❌ 拉取截图失败: {msg}")
                return False
                
        except Exception as e:
            print(f"❌ 截图异常: {e}")
            return False
    
    def launch_app(self, package_name: str, activity_name: Optional[str] = None) -> bool:
        """
        启动应用
        
        Args:
            package_name: 应用包名
            activity_name: Activity 名称，None 则启动主 Activity
        
        Returns:
            是否成功
        """
        if activity_name:
            component = f"{package_name}/{activity_name}"
        else:
            component = package_name
        
        success, msg = self._run_adb_command([
            'shell', 'monkey', '-p', package_name, '-c', 'android.intent.category.LAUNCHER', '1'
        ])
        
        if success:
            print(f"✅ 启动应用: {package_name}")
            time.sleep(2)  # 等待应用启动
            return True
        else:
            # 备用方法：使用 am start
            success2, msg2 = self._run_adb_command([
                'shell', 'am', 'start', '-n', component
            ])
            if success2:
                print(f"✅ 启动应用: {package_name}")
                time.sleep(2)
                return True
            else:
                print(f"❌ 启动应用失败: {msg2}")
                return False
    
    def get_ui_hierarchy(self, output_file: str = 'ui.xml') -> bool:
        """
        获取 UI 层次结构（用于查找元素坐标）
        
        Args:
            output_file: 输出文件名
        
        Returns:
            是否成功
        """
        device_path = '/sdcard/ui.xml'
        success, msg = self._run_adb_command(['shell', 'uiautomator', 'dump', device_path])
        
        if not success:
            print(f"❌ 获取 UI 层次失败: {msg}")
            return False
        
        # 拉取到本地
        success, msg = self._run_adb_command(['pull', device_path, output_file])
        
        if success:
            # 删除设备上的文件
            self._run_adb_command(['shell', 'rm', device_path])
            print(f"✅ UI 层次已保存: {output_file}")
            print("   提示: 打开 XML 文件查找元素的 bounds 属性获取坐标")
            return True
        else:
            print(f"❌ 拉取 UI 层次失败: {msg}")
            return False
    
    def get_screen_size(self) -> Tuple[int, int]:
        """获取屏幕尺寸"""
        if self.screen_width and self.screen_height:
            return self.screen_width, self.screen_height
        else:
            self._get_screen_size()
            return self.screen_width, self.screen_height
    
    def wait(self, seconds: float):
        """等待指定时间"""
        time.sleep(seconds)
    
    def get_current_package(self) -> Optional[str]:
        """获取当前前台应用的包名"""
        success, msg = self._run_adb_command([
            'shell', 'dumpsys', 'window', 'windows', '|', 'grep', '-E', 'mCurrentFocus'
        ])
        
        if success and msg:
            # 解析输出，格式通常是: mCurrentFocus=Window{... com.package.name/...}
            try:
                if 'mCurrentFocus' in msg:
                    parts = msg.split()
                    for part in parts:
                        if '/' in part and '.' in part:
                            package = part.split('/')[0].split('}')[-1]
                            return package
            except:
                pass
        
        return None


# 常用按键码常量
class KeyCode:
    """Android 按键码常量"""
    BACK = 4          # 返回键
    HOME = 3          # Home 键
    MENU = 82         # 菜单键
    VOLUME_UP = 24    # 音量+
    VOLUME_DOWN = 25  # 音量-
    POWER = 26        # 电源键
    ENTER = 66        # 回车键
    DELETE = 67       # 删除键
