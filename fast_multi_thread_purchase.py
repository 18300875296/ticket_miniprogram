"""
定时多线程快速抢票脚本
使用内存检测 + 多线程并发，最大化速度

核心流程：
1. 时间对齐：等待到指定时间（提前进入时间）
2. 多线程并行检测：每个阶段独立线程，同时检测所有阶段
3. 自动执行任务：检测到阶段后立即执行对应任务（如点击按钮）
4. 阶段配置：每个阶段包含采样点配置和执行任务，灵活可扩展

优化说明：
- 使用共享变量存储最新截图，确保检测始终基于最新状态
- 多线程并行检测所有阶段，最大化响应速度
- 支持自定义采样点配置，灵活检测页面状态
- 检测到阶段后自动执行任务，无需手动控制
- 随机点击延迟，模拟人类操作
"""
from adb_automation import ADBAutomation
import time
import threading
import random
from io import BytesIO
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
import os

try:
    from PIL import Image
    import numpy as np
    PIL_AVAILABLE = True
    NUMPY_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    NUMPY_AVAILABLE = False
    print("⚠️ 警告: PIL/Pillow 或 numpy 未安装，像素检测功能将不可用")
    print("   安装命令: pip install Pillow numpy")

# ========== 阶段配置（包含检测点和任务）==========
# 格式说明：
# - 每个阶段包含：阶段名称、采样点配置、执行任务
# - 采样点格式：(坐标(x,y), 目标颜色(r,g,b)或None, 容差)
#   - 如果目标颜色为None，表示蒙层检测（RGB值接近，差值小于容差）
#   - 如果目标颜色不为None，表示颜色匹配检测
# - 任务格式：{'type': 'click', 'x': int, 'y': int} 或其他任务类型
# - next_stage: 检测到后进入的下一个阶段（None表示最后阶段）

STAGE_CONFIGS = {
    'stage1': {
        'name': '详情页',
        'detectors': [
            ((272, 2035), (17, 17, 17), 10),   # #111111 ✅ 匹配
            ((811, 2024), (17, 17, 17), 10),   # #111111 ✅ 匹配
            ((604, 2047), (196, 196, 196), 15), # 实际颜色 RGB(196, 196, 196)，容差15
        ],
        'action': {
            'type': 'click',
            'x': 540,
            'y': 2044,  # 立即购买按钮
        },
        'next_stage': 'stage2',
    },
    'stage2': {
        'name': '支付页',
        'detectors': [
            ((171, 1958), (17, 17, 17), 10),   # #111111
            ((584, 1947), (17, 17, 17), 10),   # #111111
            ((520, 1959), (255, 255, 255), 10), # #ffff (白色)
        ],
        'action': {
            'type': 'click',
            'x': 485,
            'y': 1940,  # 确认按钮
        },
        'next_stage': 'stage3',
    },
    'stage3': {
        'name': '确认信息页',
        'detectors': [
            ((514, 2065), (230, 0, 32), 10),   # #E60020 (红色)
            ((656, 2071), (17, 17, 17), 10),   # #111111
        ],
        'action': {
            'type': 'click',
            'x': 771,
            'y': 2050,  # 确认信息并支付按钮
        },
        'next_stage': 'stage4',
    },
    'stage4': {
        'name': '弹框页',
        'detectors': [
            ((327, 1394), (17, 17, 17), 10),   # #111111
            ((709, 1378), (17, 17, 17), 10),   # #111111
        ],
        'action': {
            'type': 'click',
            'x': 461,
            'y': 1362,  # 确认无误按钮（弹框上的）
        },
        'next_stage': None,  # 最后阶段
    },
}



# ========== 定时抢购配置 ==========
PAGE_LOAD_TIME = 0.2  # 页面加载时间（秒），提前进入时间
MAX_STAGE_DURATION = 8.0  # 每个阶段最多轮询时长（秒）

# ========== 点击配置（防脚本检测）==========
CLICK_INTERVAL_MIN = 0.08   # 最小点击间隔（秒）
CLICK_INTERVAL_MAX = 0.18   # 最大点击间隔（秒）
CLICK_COORD_OFFSET = 8      # 坐标随机偏移范围（像素）

# ========== 性能优化配置 ==========
SCREENSHOT_INTERVAL = 0.10   # 截图间隔（秒），根据实际硬件能力调整（adb screencap通常需要80-150ms）
DETECTION_INTERVAL = 0.02    # 检测间隔（秒），可以比截图快，因为只是读取内存中的图片

# ========== 调试配置 ==========
DEBUG_MODE = True           # 是否启用调试模式（显示详细检测信息）
DEBUG_SAVE_SCREENSHOTS = True # 是否保存截图用于调试（保存在 temp_screenshots 目录）
DEBUG_DETECTION_LOG = True   # 是否输出检测日志（避免刷屏）


class TimedMultiThreadPurchase:
    """定时多线程快速抢票类"""
    
    def __init__(self, auto: ADBAutomation):
        self.auto = auto
        
        # 屏幕尺寸（初始化时获取一次，避免重复调用）
        print("📱 获取屏幕尺寸...")
        self.screen_width, self.screen_height = self.auto.get_screen_size()
        print(f"✅ 屏幕尺寸: {self.screen_width}x{self.screen_height}")
        
        # 内存截图系统（使用锁保护）
        self.frame_lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None  # 最新截图帧（numpy array）
        self.latest_png_data: Optional[bytes] = None    # 最新PNG数据（用于保存截图）
        
        # 调试相关
        self.debug_screenshot_dir = "temp_screenshots"
        if DEBUG_SAVE_SCREENSHOTS:
            os.makedirs(self.debug_screenshot_dir, exist_ok=True)
        
        # 阶段状态管理
        self.current_stage: Optional[str] = None  # 当前阶段名称
        self.stage_lock = threading.Lock()  # 阶段状态锁
        self.stage_executed = set()  # 已执行的阶段（避免重复执行）
        self.stage_action_active = {}  # 阶段动作是否在活跃执行中（用于循环点击）
        self.stage_enter_time = {}  # 【修复问题2】阶段进入时间（用于最小驻留时间）
        
        # 控制标志
        self.running = threading.Event()
        self.running.set()  # 默认运行
        
        # 统计信息
        self.stats = {
            'screenshots': 0,
            'stage_detections': {},  # 每个阶段的检测次数
            'stage_actions': {},     # 每个阶段的执行次数
        }
        self.stats_lock = threading.Lock()  # 【修复问题4】统计信息锁
    
    def update_stats(self, key: str, value: int = 1):
        """更新统计信息"""
        if key in self.stats:
            if isinstance(self.stats[key], dict):
                # 字典类型的统计，需要额外参数
                pass
            else:
                self.stats[key] += value
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()
    
    # ---------- 基础工具方法 ----------
    def _tap(self, x: int, y: int):
        """点击坐标（带随机偏移）"""
        offset_x = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
        offset_y = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
        self.auto._run_adb_command(['shell', 'input', 'tap', str(x + offset_x), str(y + offset_y)])
    
    def _png_bytes_to_numpy(self, png_data: bytes) -> Optional[np.ndarray]:
        """
        将 PNG bytes 转换为 numpy array（RGBA格式）
        
        Args:
            png_data: PNG 格式的字节数据
            
        Returns:
            numpy array (height, width, 4) RGBA格式，失败返回 None
        """
        if not PIL_AVAILABLE or not NUMPY_AVAILABLE:
            return None
        
        try:
            # 从 bytes 加载图片
            img = Image.open(BytesIO(png_data))
            
            # 转换为 RGBA 模式（确保有 alpha 通道）
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 转换为 numpy array
            frame = np.array(img)
            
            return frame
        except Exception as e:
            print(f"❌ PNG 解码失败: {e}")
            return None
    
    def _get_latest_frame(self) -> Optional[np.ndarray]:
        """获取最新截图帧（线程安全）"""
        with self.frame_lock:
            return self.latest_frame
    
    def debug_check_detection_points(self):
        """
        调试功能：检查所有检测点的实际颜色值
        """
        frame = self._get_latest_frame()
        if frame is None:
            print("❌ 没有可用的截图")
            return
        
        print("\n" + "=" * 60)
        print("🔍 检测点颜色调试信息")
        print("=" * 60)
        print(f"截图尺寸: {frame.shape[1]}x{frame.shape[0]}")
        print()
        
        for stage_name, config in STAGE_CONFIGS.items():
            print(f"📋 阶段: {config['name']} ({stage_name})")
            detectors = config.get('detectors', [])
            
            if not detectors:
                print("  ⚠️ 没有配置检测点")
                print()
                continue
            
            for i, ((x, y), target, tol) in enumerate(detectors, 1):
                # 边界检查
                if y >= frame.shape[0] or x >= frame.shape[1]:
                    print(f"  检测点{i}: ({x}, {y}) ❌ 超出截图范围")
                    continue
                
                # 获取实际颜色
                r, g, b = frame[y, x][:3]
                
                if target is None:
                    # 蒙层检测
                    print(f"  检测点{i}: ({x}, {y}) - 蒙层检测")
                    print(f"    实际颜色: RGB({r}, {g}, {b})")
                    print(f"    容差: {tol}")
                else:
                    # 颜色匹配检测
                    diff = [abs(r - target[0]), abs(g - target[1]), abs(b - target[2])]
                    max_diff = max(diff)
                    is_match = self._color_close((r, g, b), target, tol)
                    status = "✅ 匹配" if is_match else "❌ 不匹配"
                    
                    print(f"  检测点{i}: ({x}, {y}) - 颜色匹配")
                    print(f"    实际颜色: RGB({r}, {g}, {b})")
                    print(f"    目标颜色: RGB{target}")
                    print(f"    容差: {tol}, 最大差值: {max_diff}")
                    print(f"    状态: {status}")
            
            print()
        
        print("=" * 60)
        
        # 保存当前截图
        if DEBUG_SAVE_SCREENSHOTS:
            try:
                with self.frame_lock:
                    png_data = self.latest_png_data
                if png_data:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                    filename = os.path.join(self.debug_screenshot_dir, f"debug_check_{timestamp}.png")
                    with open(filename, 'wb') as f:
                        f.write(png_data)
                    print(f"💾 当前截图已保存: {filename}")
            except Exception as e:
                print(f"⚠️ 保存截图失败: {e}")
    
    def _color_close(self, c1: Tuple[int, int, int], c2: Tuple[int, int, int], tolerance: int) -> bool:
        """判断两个颜色是否接近"""
        return all(abs(c1[i] - c2[i]) <= tolerance for i in range(3))
    
    def _detect_stage(self, frame: np.ndarray, stage_name: str) -> bool:
        detectors = STAGE_CONFIGS[stage_name]['detectors']
        if not detectors:
            return False

        overlay_samples = []
        normal_samples = []

        for (x, y), target, tol in detectors:
            if target is None:
                overlay_samples.append((x, y, tol))
            else:
                normal_samples.append((x, y, target, tol))

        # —— 蒙层检测（颜色一致性）——
        if overlay_samples:
            base = None
            debug_info = []
            for x, y, tol in overlay_samples:
                # 边界检查
                if y >= frame.shape[0] or x >= frame.shape[1]:
                    if DEBUG_DETECTION_LOG:
                        print(f"⚠️ 检测点超出范围: ({x}, {y}), 截图尺寸: {frame.shape[1]}x{frame.shape[0]}")
                    return False
                
                r, g, b = frame[y, x][:3]
                if base is None:
                    base = (r, g, b)
                    debug_info.append(f"基准点({x},{y}): RGB({r},{g},{b})")
                else:
                    is_close = self._color_close(base, (r, g, b), tol)
                    debug_info.append(f"点({x},{y}): RGB({r},{g},{b}) {'✅' if is_close else '❌'}")
                    if not is_close:
                        if DEBUG_DETECTION_LOG:
                            print(f"🔍 [{stage_name}] 蒙层检测失败:")
                            for info in debug_info:
                                print(f"   {info}")
                        return False
            
            if DEBUG_DETECTION_LOG and DEBUG_MODE:
                print(f"✅ [{stage_name}] 蒙层检测通过: {len(overlay_samples)} 个点颜色一致")

        # —— 普通颜色检测 ——
        for x, y, target, tol in normal_samples:
            # 边界检查
            if y >= frame.shape[0] or x >= frame.shape[1]:
                if DEBUG_DETECTION_LOG:
                    print(f"⚠️ 检测点超出范围: ({x}, {y}), 截图尺寸: {frame.shape[1]}x{frame.shape[0]}")
                return False
            
            r, g, b = frame[y, x][:3]
            is_match = self._color_close((r, g, b), target, tol)
            
            if DEBUG_DETECTION_LOG and DEBUG_MODE:
                diff = [abs(r - target[0]), abs(g - target[1]), abs(b - target[2])]
                max_diff = max(diff)
                status = "✅" if is_match else "❌"
                print(f"🔍 [{stage_name}] 点({x},{y}): 实际RGB({r},{g},{b}) vs 目标RGB{target} "
                      f"容差={tol} 最大差值={max_diff} {status}")
            
            if not is_match:
                return False

        return True

    def _execute_stage_action(self, stage_name: str):
        """
        执行阶段对应的任务（支持循环点击）
        
        Args:
            stage_name: 阶段名称
        """
        config = STAGE_CONFIGS[stage_name]
        action = config.get('action')
        
        if not action:
            return
        
        action_type = action.get('type')
        
        # 【修复问题6】支持循环点击：在阶段内持续点击，直到进入下一阶段
        if action_type == 'click':
            x = action['x']
            y = action['y']
            
            # 检查是否已经在执行中（避免重复启动循环）
            with self.stage_lock:
                if stage_name in self.stage_action_active:
                    return  # 已经在执行中，不重复启动
                self.stage_action_active[stage_name] = True
            
            # 首次执行
            if stage_name not in self.stage_executed:
                with self.stage_lock:
                    self.stage_executed.add(stage_name)
                print(f"🎯 开始执行阶段任务 [{config['name']}]: 循环点击 ({x}, {y})")
            
            # 【修复问题3】获取期望的下一阶段
            expected_next_stage = config.get('next_stage')
            
            # 循环点击直到进入下一阶段或停止
            click_count = 0
            while self.running.is_set():
                # 【修复问题3】检查是否已经确定进入下一阶段（而不是仅仅"不是当前阶段"）
                with self.stage_lock:
                    current = self.current_stage
                    if current == expected_next_stage:
                        # 确定进入下一阶段，停止点击
                        break
                    elif current != stage_name and current is not None:
                        # 进入了其他阶段（可能是误判后被纠正），继续点击
                        pass
                
                # 执行点击
                self._tap(x, y)
                click_count += 1
                
                # 【修复问题4】线程安全的统计更新
                with self.stats_lock:
                    if stage_name not in self.stats['stage_actions']:
                        self.stats['stage_actions'][stage_name] = 0
                    self.stats['stage_actions'][stage_name] += 1
                
                # 随机延迟（模拟人类操作）
                delay = random.uniform(CLICK_INTERVAL_MIN, CLICK_INTERVAL_MAX)
                time.sleep(delay)
            
            # 清理活跃状态
            with self.stage_lock:
                self.stage_action_active.pop(stage_name, None)
            
            if click_count > 0:
                print(f"✅ 阶段任务完成 [{config['name']}]: 共点击 {click_count} 次")
        
        # 可以扩展其他任务类型
        # elif action_type == 'swipe':
        #     ...
        # elif action_type == 'wait':
        #     ...
    
    def thread_screenshot_loop(self):
        """
        截图线程：持续获取截图并转换为内存中的 numpy array
        优化：直接使用内存，避免文件 I/O
        """
        consecutive_failures = 0
        max_failures = 5
        screenshot_count = 0
        last_status_time = time.time()
        
        print("📸 截图线程开始运行...")
        
        while self.running.is_set():
            try:
                # 获取原始 PNG 数据（直接从 ADB 获取，不经过文件）
                png_data = self.auto.get_screenshot_data()
                if not png_data:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        print(f"⚠️ 连续 {consecutive_failures} 次截图失败，暂停 0.5 秒")
                        time.sleep(0.5)
                        consecutive_failures = 0
                    else:
                        time.sleep(0.05)
                    continue
                
                # 重置失败计数
                consecutive_failures = 0
                
                # 转换为 numpy array（RGBA 格式）
                frame = self._png_bytes_to_numpy(png_data)
                if frame is None:
                    print("⚠️ PNG 解码失败")
                    time.sleep(0.05)
                    continue
                
                # 验证尺寸（防止尺寸不匹配）
                if frame.shape[0] != self.screen_height or frame.shape[1] != self.screen_width:
                    print(f"⚠️ 截图尺寸不匹配: 期望 {self.screen_width}x{self.screen_height}, "
                          f"实际 {frame.shape[1]}x{frame.shape[0]}")
                    time.sleep(0.05)
                    continue
                
                # 更新最新帧和PNG数据（线程安全）
                with self.frame_lock:
                    self.latest_frame = frame
                    self.latest_png_data = png_data  # 保存PNG数据用于调试
                
                # 更新统计
                screenshot_count += 1
                with self.stats_lock:
                    self.stats['screenshots'] += 1
                
                # 调试：保存截图（每10张保存一次，避免文件过多）
                if DEBUG_SAVE_SCREENSHOTS and screenshot_count % 10 == 0:
                    try:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                        filename = os.path.join(self.debug_screenshot_dir, f"debug_{timestamp}.png")
                        with open(filename, 'wb') as f:
                            f.write(png_data)
                        if DEBUG_MODE:
                            print(f"💾 已保存调试截图: {filename}")
                    except Exception as e:
                        if DEBUG_MODE:
                            print(f"⚠️ 保存调试截图失败: {e}")
                
                # 每10秒输出一次状态（避免刷屏）
                current_time = time.time()
                if current_time - last_status_time >= 10.0:
                    print(f"📸 截图线程运行中... 已获取 {screenshot_count} 张截图")
                    last_status_time = current_time
                
                # 按配置的间隔等待
                time.sleep(SCREENSHOT_INTERVAL)

            except Exception as e:
                print(f"❌ 截图线程错误: {e}")
                import traceback
                traceback.print_exc()
                consecutive_failures += 1
                time.sleep(0.05)

    def thread_detect_stage(self, stage_name: str):
        """
        阶段检测线程：持续检测指定阶段（带阶段门禁）
        
        Args:
            stage_name: 阶段名称
        """
        config = STAGE_CONFIGS.get(stage_name)
        if not config:
            return
        
        print(f"🔍 启动阶段检测线程: {config['name']} ({stage_name})")
        
        # 【修复问题2】最小驻留时间（秒）
        MIN_STAGE_DURATION = 0.15  # 150ms，真实人类操作的时间尺度
        
        while self.running.is_set():
            try:
                # 【修复问题1和问题7】阶段门禁：只允许检测当前阶段或下一个阶段
                with self.stage_lock:
                    current = self.current_stage
                    
                    # 【修复问题2】如果当前阶段存在，检查最小驻留时间
                    if current is not None:
                        enter_time = self.stage_enter_time.get(current, 0)
                        elapsed = time.perf_counter() - enter_time
                        if elapsed < MIN_STAGE_DURATION:
                            # 当前阶段驻留时间不足，不允许切换到下一阶段
                            time.sleep(DETECTION_INTERVAL)
                            continue
                    
                    # 如果当前阶段为空，只允许检测第一个阶段（stage1）
                    if current is None:
                        # 找到第一个阶段（按STAGE_CONFIGS的顺序）
                        first_stage = list(STAGE_CONFIGS.keys())[0]
                        if stage_name != first_stage:
                            time.sleep(DETECTION_INTERVAL)
                            continue
                    else:
                        # 只允许检测：当前阶段 或 当前阶段的下一阶段
                        expected_next = STAGE_CONFIGS.get(current, {}).get('next_stage')
                        allowed_stages = {current, expected_next}
                        if stage_name not in allowed_stages:
                            # 不在允许范围内，跳过检测
                            time.sleep(DETECTION_INTERVAL)
                            continue
                    
                    # 如果当前已经是这个阶段，跳过检测（避免重复）
                    if current == stage_name:
                        time.sleep(DETECTION_INTERVAL)
                        continue
                
                # 获取最新截图帧（内存中，无需文件 I/O）
                frame = self._get_latest_frame()
                if frame is None:
                    # 截图还未就绪，等待
                    time.sleep(DETECTION_INTERVAL)
                    continue
                
                # 检测阶段（直接使用 numpy array）
                detected = self._detect_stage(frame, stage_name)
                
                # 调试：如果检测到阶段，保存截图
                if detected and DEBUG_SAVE_SCREENSHOTS:
                    try:
                        with self.frame_lock:
                            png_data = self.latest_png_data
                        if png_data:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                            filename = os.path.join(self.debug_screenshot_dir, f"detected_{stage_name}_{timestamp}.png")
                            with open(filename, 'wb') as f:
                                f.write(png_data)
                            if DEBUG_MODE:
                                print(f"💾 检测到阶段，已保存截图: {filename}")
                    except Exception as e:
                        if DEBUG_MODE:
                            print(f"⚠️ 保存检测截图失败: {e}")
                
                if detected:
                    with self.stage_lock:
                        # 双重检查：再次确认阶段门禁（防止并发问题）
                        current = self.current_stage
                        
                        # 【修复问题2】再次检查最小驻留时间
                        if current is not None:
                            enter_time = self.stage_enter_time.get(current, 0)
                            elapsed = time.perf_counter() - enter_time
                            if elapsed < MIN_STAGE_DURATION:
                                continue
                        
                        if current is None:
                            first_stage = list(STAGE_CONFIGS.keys())[0]
                            if stage_name != first_stage:
                                continue
                        else:
                            expected_next = STAGE_CONFIGS.get(current, {}).get('next_stage')
                            if stage_name not in {current, expected_next}:
                                continue
                        
                        # 检查是否已经进入其他阶段（防止重复执行）
                        if self.current_stage != stage_name:
                            print(f"✅ 检测到阶段: {config['name']} ({stage_name})")
                            
                            # 【修复问题2】更新当前阶段和进入时间
                            self.current_stage = stage_name
                            self.stage_enter_time[stage_name] = time.perf_counter()
                            
                            # 【修复问题4】线程安全的统计更新
                            with self.stats_lock:
                                if stage_name not in self.stats['stage_detections']:
                                    self.stats['stage_detections'][stage_name] = 0
                                self.stats['stage_detections'][stage_name] += 1
                            
                            # 在新线程中执行阶段任务（避免阻塞检测）
                            action_thread = threading.Thread(
                                target=self._execute_stage_action,
                                args=(stage_name,),
                                daemon=True
                            )
                            action_thread.start()
                
                time.sleep(DETECTION_INTERVAL)
                
            except Exception as e:
                print(f"❌ 阶段检测线程错误 ({stage_name}): {e}")
                time.sleep(0.1)
    
    # ---------- 阶段化执行 ----------
    def wait_until_time(self, target_time: datetime):
        """
        等待到指定时间（提前PAGE_LOAD_TIME进入）
        
        Args:
            target_time: 目标时间（datetime对象）
        """
        now = datetime.now()
        if target_time <= now:
            print(f"⚠️ 目标时间已过，立即开始")
            return
        
        # 提前PAGE_LOAD_TIME进入
        enter_time = target_time - timedelta(seconds=PAGE_LOAD_TIME)
        wait_seconds = (enter_time - now).total_seconds()
        
        if wait_seconds > 0:
            print(f"⏰ 等待到 {target_time.strftime('%H:%M:%S')}（提前{PAGE_LOAD_TIME*1000:.0f}ms进入）")
            print(f"   当前时间: {now.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"   进入时间: {enter_time.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"   等待时长: {wait_seconds:.1f}秒")
            
            # 如果等待时间较长，定期输出状态
            if wait_seconds > 10:
                print("💡 等待期间，截图和检测线程在后台运行...")
                last_status_time = time.time()
                status_interval = 10.0  # 每10秒输出一次
                
                while wait_seconds > 0:
                    sleep_time = min(1.0, wait_seconds)  # 每次最多睡1秒
                    time.sleep(sleep_time)
                    wait_seconds -= sleep_time
                    
                    # 定期输出状态
                    current_time = time.time()
                    if current_time - last_status_time >= status_interval:
                        remaining = wait_seconds
                        frame = self._get_latest_frame()
                        frame_status = "✅" if frame is not None else "⏳"
                        with self.stats_lock:
                            screenshot_count = self.stats['screenshots']
                        print(f"   ⏳ 剩余等待: {remaining:.1f}秒 | 截图状态: {frame_status} | 已截图: {screenshot_count} 张")
                        last_status_time = current_time
            else:
                # 等待时间短，直接等待
                time.sleep(wait_seconds)
            
            print(f"✅ 已到达进入时间: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        else:
            print(f"⚠️ 进入时间已过，立即开始")
    
    def run_timed_purchase(self, target_time: datetime, initial_stage: str = None):
        """
        执行定时抢购流程（多线程并行检测版本）
        
        Args:
            target_time: 目标抢购时间（datetime对象）
            initial_stage: 初始阶段名称（如果已知当前处于哪个阶段）
                           【修复问题1】如果提前进入详情页，应该设置为 "stage1"
        """
        print("\n" + "=" * 60)
        print("🚀 定时多线程快速抢票启动（并行检测模式）")
        print("=" * 60)
        print(f"⏰ 目标时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 页面加载时间: {PAGE_LOAD_TIME*1000:.0f}ms（提前进入）")
        
        # 打印阶段配置
        print("\n📋 阶段配置:")
        for stage_name, config in STAGE_CONFIGS.items():
            print(f"  - {config['name']} ({stage_name}):")
            print(f"    采样点: {len(config['detectors'])} 个")
            for i, (point, color, tolerance) in enumerate(config['detectors'], 1):
                if color is None:
                    print(f"      采样点{i}: {point}, 蒙层检测(容差={tolerance})")
                else:
                    print(f"      采样点{i}: {point}, 颜色{color}(容差={tolerance})")
            if config.get('action'):
                action = config['action']
                if action.get('type') == 'click':
                    print(f"    任务: 点击 ({action['x']}, {action['y']})")
            if config.get('next_stage'):
                print(f"    下一阶段: {config['next_stage']}")
            else:
                print(f"    下一阶段: 无（最后阶段）")
        print("=" * 60)
        
        overall_start_time = time.perf_counter()
        
        # 启动截图线程
        screenshot_thread = threading.Thread(target=self.thread_screenshot_loop, daemon=True)
        screenshot_thread.start()
        print("\n✅ 截图线程已启动")
        
        # 等待截图就绪，并验证
        print("⏳ 等待截图就绪...")
        for i in range(10):  # 最多等待2秒
            time.sleep(0.2)
            frame = self._get_latest_frame()
            if frame is not None:
                print(f"✅ 截图已就绪 (尺寸: {frame.shape[1]}x{frame.shape[0]})")
                # 调试：检查检测点颜色
                if DEBUG_MODE:
                    print("\n🔍 执行初始检测点检查...")
                    self.debug_check_detection_points()
                break
        else:
            print("⚠️ 警告: 截图未就绪，但继续运行（可能截图线程有问题）")
        
        # 【修复问题1】设置初始阶段（如果未指定且stage1没有detector，默认设为stage1）
        if initial_stage is None:
            # 检查stage1是否有detector
            stage1_config = STAGE_CONFIGS.get('stage1', {})
            stage1_detectors = stage1_config.get('detectors', [])
            if not stage1_detectors:
                # stage1没有detector，默认设为stage1（假设提前进入详情页）
                initial_stage = 'stage1'
                print("⚠️  stage1 没有配置 detector，默认假设当前已在 stage1（详情页）")
        
        if initial_stage:
            with self.stage_lock:
                self.current_stage = initial_stage
                # 【修复问题2】设置初始阶段的进入时间
                self.stage_enter_time[initial_stage] = time.perf_counter()
            print(f"📌 初始阶段: {initial_stage}")
        
        # 启动所有阶段的检测线程
        detection_threads = []
        for stage_name in STAGE_CONFIGS.keys():
            thread = threading.Thread(
                target=self.thread_detect_stage,
                args=(stage_name,),
                daemon=True
            )
            thread.start()
            detection_threads.append(thread)
        
        print(f"✅ 已启动 {len(detection_threads)} 个阶段检测线程")
        
        # 等待到指定时间
        self.wait_until_time(target_time)
        
        print("\n" + "=" * 60)
        print("🎯 开始抢购流程（多线程并行检测）")
        print("=" * 60)
        
        try:
            # 持续运行，直到所有阶段完成或手动停止
            # 可以通过检查 current_stage 来判断是否完成
            last_status_time = time.time()
            status_interval = 5.0  # 每5秒输出一次状态
            
            while self.running.is_set():
                time.sleep(0.1)
                
                # 定期输出状态
                current_time = time.time()
                if current_time - last_status_time >= status_interval:
                    with self.stage_lock:
                        current = self.current_stage
                    with self.stats_lock:
                        stats = self.get_stats()
                    
                    frame = self._get_latest_frame()
                    frame_status = "✅" if frame is not None else "❌"
                    
                    print(f"📊 状态: 当前阶段={current or '未知'}, "
                          f"截图={frame_status}, "
                          f"截图数={stats['screenshots']}, "
                          f"检测次数={sum(stats['stage_detections'].values())}")
                    last_status_time = current_time
                
                # 检查是否完成所有阶段
                with self.stage_lock:
                    current = self.current_stage
                    if current:
                        config = STAGE_CONFIGS.get(current)
                        if config and not config.get('next_stage'):
                            # 最后一个阶段，可以结束
                            print(f"\n✅ 已完成所有阶段，当前在: {config['name']}")
                            time.sleep(1.0)  # 等待最后操作完成
                            break
        
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断，正在停止...")
            self.running.clear()
        
        # 停止运行
        self.running.clear()
        
        # 等待线程结束
        screenshot_thread.join(timeout=1.0)
        for thread in detection_threads:
            thread.join(timeout=1.0)
        
        total_time = time.perf_counter() - overall_start_time
        stats = self.get_stats()
        
        print("\n" + "=" * 60)
        print("📊 最终统计")
        print("=" * 60)
        print(f"⏱️  总运行时间: {total_time:.2f} 秒")
        print(f"📸 截图次数: {stats['screenshots']}")
        print(f"🔍 阶段检测次数:")
        for stage_name, count in stats['stage_detections'].items():
            config = STAGE_CONFIGS.get(stage_name, {})
            print(f"  - {config.get('name', stage_name)}: {count} 次")
        print(f"🎯 阶段执行次数:")
        for stage_name, count in stats['stage_actions'].items():
            config = STAGE_CONFIGS.get(stage_name, {})
            print(f"  - {config.get('name', stage_name)}: {count} 次")
        print("=" * 60)
    
    def run(self, duration: float = 30.0):
        """
        兼容旧接口：立即运行（不等待时间）
        
        Args:
            duration: 运行时长（秒），0 表示无限运行
        """
        # 立即开始
        target_time = datetime.now()
        self.run_timed_purchase(target_time)


def main():
    """主函数"""
    # 检查 PIL 是否可用
    if not PIL_AVAILABLE:
        print("❌ 错误: PIL/Pillow 未安装，程序无法运行")
        print("   请先安装: pip install Pillow")
        return
    
    auto = ADBAutomation()
    
    if not auto.connect():
        print("❌ 设备连接失败")
        return
    
    purchase = TimedMultiThreadPurchase(auto)
    
    # 示例：设置9点开抢
    # 方式1：使用今天的9点
    now = datetime.now()
    target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if target_time <= now:
        # 如果今天9点已过，设置为明天9点
        target_time += timedelta(days=1)
    
    # 方式2：手动指定时间
    # target_time = datetime(2025, 1, 22, 9, 0, 0)  # 2025-01-22 09:00:00
    
    # 方式3：立即开始（用于测试）
    # target_time = datetime.now()
    
    print(f"🎯 目标抢购时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 【修复问题1】如果提前进入详情页等待，应该指定 initial_stage="stage1"
    # 这样即使 stage1 没有 detector，也能正常启动流程
    purchase.run_timed_purchase(target_time, initial_stage="stage1")


if __name__ == "__main__":
    main()
