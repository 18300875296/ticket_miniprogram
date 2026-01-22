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

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ 警告: PIL/Pillow 未安装，像素检测功能将不可用")
    print("   安装命令: pip install Pillow")

# ========== 按钮坐标配置 ==========
DETAIL_BOTTOM_X = 505
DETAIL_BOTTOM_Y = 2140
PAY_BUTTON_X = 825
PAY_BUTTON_Y = 2260
POPUP_CONFIRM_X = 585
POPUP_CONFIRM_Y = 1545

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
            # 在这里添加详情页的唯一标识采样点
            # 示例：((100, 100), (255, 255, 255), 10),
        ],
        'action': {
            'type': 'click',
            'x': DETAIL_BOTTOM_X,
            'y': DETAIL_BOTTOM_Y,
        },
        'next_stage': 'stage2',
    },
    'stage2': {
        'name': '支付页',
        'detectors': [
            ((PAY_BUTTON_X, PAY_BUTTON_Y), (0, 0, 0), 18),  # 需要根据实际情况修改颜色
        ],
        'action': {
            'type': 'click',
            'x': PAY_BUTTON_X,
            'y': PAY_BUTTON_Y,
        },
        'next_stage': 'stage3',
    },
    'stage3': {
        'name': '弹框页',
        'detectors': [
            ((100, 300), None, 8),   # 蒙层检测
            ((980, 300), None, 8),
            ((100, 2040), None, 8),
            ((980, 2040), None, 8),
        ],
        'action': {
            'type': 'click',
            'x': POPUP_CONFIRM_X,
            'y': POPUP_CONFIRM_Y,
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


class TimedMultiThreadPurchase:
    """定时多线程快速抢票类"""
    
    def __init__(self, auto: ADBAutomation):
        self.auto = auto
        
        # 最新截图存储（使用锁保护）
        self.latest_screenshot_lock = threading.Lock()
        self.latest_screenshot_data: Optional[bytes] = None
        
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
    
    def _load_image(self, data: bytes) -> Optional[Image.Image]:
        """加载图片"""
        try:
            return Image.open(BytesIO(data))
        except Exception as e:
            print(f"❌ 加载图片失败: {e}")
            return None
    
    def _color_close(self, c1: Tuple[int, int, int], c2: Tuple[int, int, int], tolerance: int) -> bool:
        """判断两个颜色是否接近"""
        return all(abs(c1[i] - c2[i]) <= tolerance for i in range(3))
    
    def _get_latest_screenshot(self) -> Optional[bytes]:
        """获取最新截图（线程安全）"""
        with self.latest_screenshot_lock:
            return self.latest_screenshot_data
    
    def _set_latest_screenshot(self, data: bytes):
        """设置最新截图（线程安全）"""
        with self.latest_screenshot_lock:
            self.latest_screenshot_data = data
    
    # ---------- 检测逻辑 ----------
    def _detect_stage(self, img: Image.Image, stage_name: str) -> bool:
        """
        检测页面阶段（通过采样点颜色）
        
        Args:
            img: 图片对象
            stage_name: 阶段名称（在STAGE_CONFIGS中定义）
        
        Returns:
            bool: 是否匹配该阶段（所有采样点都匹配才返回True）
        """
        try:
            # 转换为RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            detectors = STAGE_CONFIGS[stage_name]['detectors']
            
            # 【修复问题2】空detector列表直接返回False，不允许空检测
            if not detectors:
                return False
            
            # 收集蒙层检测点的颜色（如果存在）
            overlay_colors = []
            normal_detectors = []
            
            for point_config in detectors:
                point, target_color, tolerance = point_config
                if target_color is None:
                    # 蒙层检测点，先收集颜色
                    overlay_colors.append((point, tolerance))
                else:
                    # 正常颜色匹配检测点
                    normal_detectors.append((point, target_color, tolerance))
            
            # 【修复问题3】处理蒙层检测：判断多个蒙层点的颜色是否彼此接近
            if overlay_colors:
                overlay_rgb_list = []
                for point, tolerance in overlay_colors:
                    x, y = point
                    try:
                        px = img.getpixel((x, y))
                        r, g, b = px[:3]
                        overlay_rgb_list.append((r, g, b, tolerance))
                    except Exception:
                        return False
                
                # 蒙层检测：所有点的RGB值应该彼此接近（低方差）
                # 计算所有点之间的颜色差异
                for i in range(len(overlay_rgb_list)):
                    r1, g1, b1, tol1 = overlay_rgb_list[i]
                    for j in range(i + 1, len(overlay_rgb_list)):
                        r2, g2, b2, tol2 = overlay_rgb_list[j]
                        # 使用两个容差中的较大值
                        max_tolerance = max(tol1, tol2)
                        if not self._color_close((r1, g1, b1), (r2, g2, b2), max_tolerance):
                            return False
            
            # 处理正常颜色匹配检测点
            for point, target_color, tolerance in normal_detectors:
                x, y = point
                try:
                    px = img.getpixel((x, y))
                    r, g, b = px[:3]
                    
                    if not self._color_close((r, g, b), target_color, tolerance):
                        return False
                except Exception:
                    return False
            
            # 所有采样点都匹配
            return True
        except Exception as e:
            print(f"❌ 阶段检测异常 ({stage_name}): {e}")
            return False
    
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
    
    # ---------- 截图线程 ----------
    def thread_screenshot_loop(self):
        """截图线程：持续轮询截图"""
        while self.running.is_set():
            try:
                # 直接获取截图到内存
                success, screenshot_data = self.auto._run_adb_command(
                    ['shell', 'screencap', '-p'],
                    timeout=3,
                    capture_binary=True
                )
                
                if success and screenshot_data:
                    # 直接覆盖最新截图（线程安全）
                    self._set_latest_screenshot(screenshot_data)
                    self.update_stats('screenshots')
                
                time.sleep(SCREENSHOT_INTERVAL)
            except Exception as e:
                print(f"❌ 截图线程错误: {e}")
                time.sleep(0.1)
    
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
                
                # 获取最新截图
                screenshot_data = self._get_latest_screenshot()
                if not screenshot_data:
                    time.sleep(DETECTION_INTERVAL)
                    continue
                
                # 加载图片并检测
                img = self._load_image(screenshot_data)
                if not img:
                    time.sleep(DETECTION_INTERVAL)
                    continue
                
                # 检测阶段
                if self._detect_stage(img, stage_name):
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
            print(f"   等待时长: {wait_seconds:.3f}秒")
            
            # 精确等待
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
        
        # 等待截图就绪
        time.sleep(0.2)
        
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
            while self.running.is_set():
                time.sleep(0.1)
                
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
