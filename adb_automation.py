"""
ADB 自动化工具类
用于通过 ADB 控制 Android 设备
"""
import subprocess
import os
from typing import Optional, Tuple, Any


class ADBAutomation:
    """ADB 自动化类"""
    
    def __init__(self, device_id: Optional[str] = None):
        """
        初始化 ADB 自动化
        
        Args:
            device_id: 设备 ID，如果为 None 则自动选择第一个设备
        """
        self.device_id = device_id
        self.adb_path = self._find_adb()
    
    def _find_adb(self) -> str:
        """查找 ADB 可执行文件"""
        # 首先尝试直接使用 adb 命令
        try:
            result = subprocess.run(
                ['adb', 'version'],
                capture_output=True,
                timeout=5,
                check=True
            )
            return 'adb'
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # 尝试从环境变量中查找
        android_home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        if android_home:
            adb_paths = [
                os.path.join(android_home, 'platform-tools', 'adb.exe'),
                os.path.join(android_home, 'platform-tools', 'adb'),
            ]
            for path in adb_paths:
                if os.path.exists(path):
                    return path
        
        # 默认返回 adb（假设在 PATH 中）
        return 'adb'
    
    def connect(self, device_id: Optional[str] = None) -> bool:
        """
        连接设备
        
        Args:
            device_id: 设备 ID，如果为 None 则使用初始化时的 device_id 或自动选择
        
        Returns:
            是否连接成功
        """
        # 如果提供了新的 device_id，更新它
        if device_id is not None:
            self.device_id = device_id
        
        try:
            # 获取设备列表
            result = subprocess.run(
                [self.adb_path, 'devices'],
                capture_output=True,
                timeout=5,
                text=True,
                check=True
            )
            
            # 解析设备列表
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            devices = []
            for line in lines[1:]:  # 跳过第一行 "List of devices attached"
                if '\tdevice' in line:
                    device = line.split('\t')[0]
                    devices.append(device)
            
            if not devices:
                print("❌ 未找到已连接的设备")
                print("   请确保：")
                print("   1. 设备已通过 USB 连接")
                print("   2. 已启用 USB 调试")
                print("   3. 已授权此计算机")
                return False
            
            # 选择设备
            if self.device_id:
                if self.device_id in devices:
                    print(f"✅ 已连接到设备: {self.device_id}")
                    return True
                else:
                    print(f"❌ 设备 {self.device_id} 未找到")
                    print(f"   可用设备: {', '.join(devices)}")
                    return False
            else:
                # 自动选择第一个设备
                self.device_id = devices[0]
                if len(devices) > 1:
                    print(f"⚠️  发现多个设备，使用: {self.device_id}")
                    print(f"   所有设备: {', '.join(devices)}")
                else:
                    print(f"✅ 已连接到设备: {self.device_id}")
                return True
                
        except subprocess.TimeoutExpired:
            print("❌ ADB 命令超时")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ ADB 命令执行失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 连接设备时出错: {e}")
            return False
    
    def _run_adb_command(
        self,
        args: list,
        timeout: int = 10,
        capture_binary: bool = False
    ) -> Tuple[bool, Any]:
        """
        运行 ADB 命令
        
        Args:
            args: ADB 命令参数（不包含 'adb' 和设备 ID）
            timeout: 超时时间（秒）
            capture_binary: 是否以二进制模式捕获输出
        
        Returns:
            (成功标志, 输出内容)
        """
        cmd = [self.adb_path]
        
        # 如果指定了设备 ID，添加 -s 参数
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        
        cmd.extend(args)
        
        try:
            if capture_binary:
                # 二进制模式
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                    text=False  # 关键：必须设置为 False 才能获取二进制数据
                )
                return (result.returncode == 0, result.stdout)
            else:
                # 文本模式
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=timeout,
                    text=True,
                    check=False
                )
                return (result.returncode == 0, result.stdout.strip())
        except subprocess.TimeoutExpired:
            return (False, "命令超时")
        except Exception as e:
            return (False, str(e))
    
    def get_screen_size(self) -> Tuple[int, int]:
        """
        获取屏幕尺寸
        
        Returns:
            (宽度, 高度)
        """
        success, output = self._run_adb_command(['shell', 'wm', 'size'])
        if success and output:
            try:
                # 输出格式: "Physical size: 1080x2400" 或 "1080x2400"
                size_str = output.split(':')[-1].strip()
                width, height = map(int, size_str.split('x'))
                return (width, height)
            except (ValueError, IndexError):
                pass
        
        # 如果获取失败，返回默认值
        print("⚠️  无法获取屏幕尺寸，使用默认值: 1080x2400")
        return (1080, 2400)
    
    def tap(self, x: int, y: int) -> bool:
        """
        点击坐标
        
        Args:
            x: X 坐标
            y: Y 坐标
        
        Returns:
            是否成功
        """
        success, _ = self._run_adb_command(['shell', 'input', 'tap', str(x), str(y)])
        return success
    
    def take_screenshot(self, filename: str) -> bool:
        """
        截图
        
        Args:
            filename: 保存的文件名
        
        Returns:
            是否成功
        """
        # 先截图到设备临时文件
        temp_path = '/sdcard/screenshot_temp.png'
        success, _ = self._run_adb_command(['shell', 'screencap', '-p', temp_path])
        
        if success:
            # 拉取文件到本地
            success, _ = self._run_adb_command(['pull', temp_path, filename])
            if success:
                # 删除设备上的临时文件
                self._run_adb_command(['shell', 'rm', temp_path])
                print(f"✅ 截图已保存: {filename}")
                return True
        
        # 如果上面的方法失败，尝试直接输出到 stdout
        success, screenshot_data = self._run_adb_command(
            ['shell', 'screencap', '-p'],
            timeout=5,
            capture_binary=True
        )
        
        if success and screenshot_data:
            try:
                with open(filename, 'wb') as f:
                    f.write(screenshot_data)
                print(f"✅ 截图已保存: {filename}")
                return True
            except Exception as e:
                print(f"❌ 保存截图失败: {e}")
                return False
        
        print("❌ 截图失败")
        return False
    
    def get_screenshot_data(self) -> Optional[bytes]:
        """
        获取截图数据（使用文件方式，避免换行符问题）
        
        Returns:
            截图数据的 bytes，失败返回 None
        """
        import tempfile
        import os
        
        # 使用临时文件方式，避免换行符问题
        temp_path = '/sdcard/screenshot_temp.png'
        success, _ = self._run_adb_command(['shell', 'screencap', '-p', temp_path])
        
        if success:
            # 拉取文件到本地临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                local_temp = tmp_file.name
            
            try:
                success, _ = self._run_adb_command(['pull', temp_path, local_temp])
                if success:
                    # 读取文件数据
                    with open(local_temp, 'rb') as f:
                        data = f.read()
                    # 删除设备上的临时文件
                    self._run_adb_command(['shell', 'rm', temp_path])
                    # 删除本地临时文件
                    try:
                        os.unlink(local_temp)
                    except:
                        pass
                    return data
            except Exception as e:
                # 清理本地临时文件
                try:
                    os.unlink(local_temp)
                except:
                    pass
                return None
        
        return None
    
    def get_ui_hierarchy(self, filename: str) -> bool:
        """
        获取 UI 层次结构
        
        Args:
            filename: 保存的文件名
        
        Returns:
            是否成功
        """
        # 方法1: 使用 uiautomator dump
        success, output = self._run_adb_command(['shell', 'uiautomator', 'dump', '/dev/tty'])
        
        if success and output:
            # 如果输出是文件路径，需要 pull
            if output.startswith('/'):
                # 输出是文件路径，需要拉取
                pull_success, _ = self._run_adb_command(['pull', output, filename])
                if pull_success:
                    # 删除设备上的临时文件
                    self._run_adb_command(['shell', 'rm', output])
                    print(f"✅ UI 层次结构已保存: {filename}")
                    return True
            else:
                # 输出是 XML 内容，直接保存
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(output)
                    print(f"✅ UI 层次结构已保存: {filename}")
                    return True
                except Exception as e:
                    print(f"❌ 保存 UI 层次结构失败: {e}")
                    return False
        
        # 方法2: 使用 uiautomator dump 到文件
        temp_path = '/sdcard/ui_dump.xml'
        success, _ = self._run_adb_command(['shell', 'uiautomator', 'dump', temp_path])
        
        if success:
            # 拉取文件
            pull_success, _ = self._run_adb_command(['pull', temp_path, filename])
            if pull_success:
                # 删除设备上的临时文件
                self._run_adb_command(['shell', 'rm', temp_path])
                print(f"✅ UI 层次结构已保存: {filename}")
                return True
        
        print("❌ 获取 UI 层次结构失败")
        return False

