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
import copy
from collections import deque

# 【优化】优先使用 OpenCV（解码速度 5-9ms vs PIL 12-25ms）
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("⚠️  OpenCV 未安装，将使用 PIL 解码（较慢）")
    print("   安装命令: pip install opencv-python")
    print("   建议安装以获得更好性能（节省 7-16ms）")

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
# - 采样点格式：(坐标(x,y), 目标颜色(r,g,b), 容差)
#   - 统一使用颜色匹配检测（RGB值在容差范围内即匹配）
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

# ========== 点击配置（防脚本检测）==========
CLICK_INTERVAL_MIN = 0.2   # 最小点击间隔（秒）
CLICK_INTERVAL_MAX = 0.3   # 最大点击间隔（秒）
CLICK_COORD_OFFSET = 8      # 坐标随机偏移范围（像素）
MAX_CLICKS_PER_STAGE = 20  # 每个阶段最大点击次数（防封号）
CLICK_BACKOFF_FACTOR = 1.1  # 点击退避因子（每次点击后延迟递增）

# ========== 性能优化配置 ==========
SCREENSHOT_INTERVAL = 0.20   # 截图间隔（秒），根据实际硬件能力调整（adb screencap通常需要80-150ms）
DETECTION_INTERVAL = 0.004   # 【优化】检测间隔（秒），降到 4ms（从 100ms 优化），页面变化立即检测

# ========== 阶段执行配置 ==========
STAGE_EXECUTION_TIMEOUT = 4.0  # 非最后阶段的执行超时时间（秒），超时后自动进入下一阶段
LAST_STAGE_EXECUTION_DURATION_MIN = 1.50  # 最后阶段最小执行时间（秒）
LAST_STAGE_EXECUTION_DURATION_MAX = 3.0  # 最后阶段最大执行时间（秒）

# ========== 调试配置 ==========
DEBUG_MODE = True           # 是否启用调试模式（显示详细检测信息）
DEBUG_SAVE_SCREENSHOTS = True # 是否保存截图用于调试（保存在 temp_screenshots 目录）
DEBUG_DETECTION_LOG = True   # 是否输出检测日志（避免刷屏）
DEBUG_CHECK_ONCE = True      # 是否只在启动时检查一次检测点（性能优化）


# ========== 真人点击节奏系统 ==========
class HumanClickRhythm:
    """
    真人点击节奏模拟器
    
    核心思想：不是"随机延迟"，而是"有情绪、有惯性、有阶段感的人"
    
    5大策略：
    1. 节奏曲线：根据阶段内时间和点击次数，动态调整目标节奏（慢启动/快速启动/稳定）
    2. 操作惯性：当前节奏不会瞬间跳变，而是平滑过渡（有动量）
    3. 反直觉停顿：偶发长延迟（300-800ms），模拟真人的"突然停顿"
    4. 阶段级节奏人格：不同阶段有不同的人设（紧张度、失误率、停顿频率）
    5. 小失误模型：偶发重复点击（2%概率），模拟真人的"没必要但真实"的错
    """
    
    def __init__(self, stage_name: str, session_persona: Optional[dict] = None):
        """
        初始化真人点击节奏系统
        
        Args:
            stage_name: 阶段名称（用于获取阶段人格配置）
            session_persona: 会话级人格（用于避免"太稳定地像人"），如果为None则使用默认
        """
        self.stage_name = stage_name
        
        # 【策略2】操作惯性：当前节奏状态
        self.current_rhythm = 0.25  # 当前节奏（秒），会惯性变化
        self.rhythm_momentum = 0.0  # 节奏动量（加速/减速趋势）
        
        # 【策略1】节奏曲线：阶段内的时间上下文
        self.stage_start_time = time.perf_counter()
        self.click_count_in_stage = 0
        
        # 【策略3】反直觉停顿：偶发长延迟
        self.last_long_pause_time = 0  # 上次长停顿时间
        self.long_pause_cooldown = 5.0  # 长停顿冷却（秒）
        
        # 【策略4】阶段级节奏人格：不同阶段不同人设
        base_personality = self._get_stage_personality(stage_name)
        
        # 【修复问题5】会话级 persona 随机：避免"太稳定地像人"
        if session_persona:
            # 应用会话级缩放因子
            self.stage_personality = {
                'name': base_personality['name'],
                'base_rhythm': base_personality['base_rhythm'] * session_persona.get('rhythm_scale', 1.0),
                'rhythm_range': (
                    base_personality['rhythm_range'][0] * session_persona.get('rhythm_scale', 1.0),
                    base_personality['rhythm_range'][1] * session_persona.get('rhythm_scale', 1.0),
                ),
                'acceleration_curve': base_personality['acceleration_curve'],
                'pause_frequency': base_personality['pause_frequency'] * session_persona.get('pause_scale', 1.0),
                'mistake_rate': base_personality['mistake_rate'] * session_persona.get('mistake_scale', 1.0),
                'tension_level': base_personality['tension_level'] * session_persona.get('tension_scale', 1.0),
            }
        else:
            self.stage_personality = base_personality
        
        # 初始化当前节奏为阶段基础节奏
        self.current_rhythm = self.stage_personality['base_rhythm']
    
    def _get_stage_personality(self, stage_name: str) -> dict:
        """
        阶段级节奏人格配置
        
        返回：{
            'name': 人格名称（用于调试），
            'base_rhythm': 基础节奏（秒），
            'rhythm_range': (min, max) 节奏范围，
            'acceleration_curve': 'slow_start' | 'fast_start' | 'steady',
            'pause_frequency': 停顿频率（0-1），
            'mistake_rate': 失误率（0-1），
            'tension_level': 紧张度（0-1），影响节奏变化幅度
        }
        """
        personalities = {
            'stage1': {
                'name': '随意等待',
                'base_rhythm': 0.35,  # 较慢
                'rhythm_range': (0.25, 0.50),
                'acceleration_curve': 'slow_start',  # 慢启动
                'pause_frequency': 0.15,  # 15% 概率停顿
                'mistake_rate': 0.01,  # 1% 失误率
                'tension_level': 0.2,  # 低紧张度
            },
            'stage2': {
                'name': '紧张加速',
                'base_rhythm': 0.20,  # 较快
                'rhythm_range': (0.15, 0.35),
                'acceleration_curve': 'fast_start',  # 快速启动
                'pause_frequency': 0.08,  # 8% 概率停顿（紧张时停顿少）
                'mistake_rate': 0.03,  # 3% 失误率（紧张时容易失误）
                'tension_level': 0.7,  # 高紧张度
            },
            'stage3': {
                'name': '谨慎确认',
                'base_rhythm': 0.28,  # 中等
                'rhythm_range': (0.20, 0.40),
                'acceleration_curve': 'steady',  # 稳定
                'pause_frequency': 0.12,  # 12% 概率停顿
                'mistake_rate': 0.02,  # 2% 失误率
                'tension_level': 0.5,  # 中等紧张度
            },
            'stage4': {
                'name': '快速确认',
                'base_rhythm': 0.22,  # 较快
                'rhythm_range': (0.18, 0.32),
                'acceleration_curve': 'fast_start',  # 快速启动
                'pause_frequency': 0.10,  # 10% 概率停顿
                'mistake_rate': 0.02,  # 2% 失误率
                'tension_level': 0.6,  # 中高紧张度
            },
        }
        return personalities.get(stage_name, personalities['stage1'])
    
    def get_next_delay(self) -> float:
        """
        获取下一次点击的延迟（核心算法）
        
        【修复问题1】统一只用一个计数源：完全基于 self.click_count_in_stage
        不再接受外部 click_count 参数，避免双源计数不一致
        
        Returns:
            延迟时间（秒）
        """
        personality = self.stage_personality
        
        # 计算阶段已执行时间
        stage_elapsed = time.perf_counter() - self.stage_start_time
        
        # 【策略1】节奏曲线：根据阶段内时间和点击次数调整目标节奏
        # 使用内部状态 self.click_count_in_stage（单一真相源）
        target_rhythm = self._calculate_target_rhythm(
            personality, self.click_count_in_stage, stage_elapsed
        )
        
        # 【策略2】操作惯性：当前节奏向目标节奏平滑过渡（不是瞬间跳变）
        self.current_rhythm = self._apply_momentum(
            self.current_rhythm, target_rhythm, personality['tension_level']
        )
        
        # 【策略3】反直觉停顿：偶发长延迟（300-800ms）
        if self._should_take_long_pause(personality, stage_elapsed):
            pause_duration = random.uniform(0.3, 0.8)
            self.last_long_pause_time = time.perf_counter()
            # 长停顿后，节奏会变慢（惯性）
            self.current_rhythm *= 1.3
            return pause_duration
        
        # 基础延迟：基于当前节奏 + 右偏分布（长尾）
        base_delay = self._sample_right_skewed_delay(
            self.current_rhythm, personality['rhythm_range']
        )
        
        return base_delay
    
    def _calculate_target_rhythm(
        self, personality: dict, click_count: int, stage_elapsed: float
    ) -> float:
        """
        【策略1】计算目标节奏（节奏曲线）
        
        根据阶段内时间和点击次数，计算当前应该的节奏
        """
        base = personality['base_rhythm']
        curve = personality['acceleration_curve']
        
        if curve == 'slow_start':
            # 慢启动：开始慢，逐渐加速
            # 前30%时间：慢，后70%：加速
            if stage_elapsed < 1.0:
                progress = min(stage_elapsed / 1.0, 1.0)
                return base * (1.0 + 0.3 * (1 - progress))  # 1.3x -> 1.0x
            else:
                return base * 0.9  # 加速到 90%
        
        elif curve == 'fast_start':
            # 快速启动：开始快，可能逐渐稳定或更快
            if click_count < 3:
                return base * 0.85  # 前3次很快
            elif click_count < 8:
                return base * 0.95  # 中间稳定
            else:
                # 连续点击后可能更快（紧张）
                return base * 0.88
        
        else:  # steady
            # 稳定：基本不变，小幅波动
            return base * random.uniform(0.95, 1.05)
    
    def _apply_momentum(
        self, current: float, target: float, tension: float
    ) -> float:
        """
        【策略2】应用操作惯性
        
        当前节奏不会瞬间跳到目标，而是平滑过渡
        紧张度越高，变化越快（但仍有惯性）
        """
        # 惯性系数：0.3-0.7（紧张时变化快，但仍需平滑）
        momentum_factor = 0.5 + tension * 0.2
        
        # 平滑过渡：current = current * (1-factor) + target * factor
        new_rhythm = current * (1 - momentum_factor) + target * momentum_factor
        
        # 更新动量（用于下一次）
        self.rhythm_momentum = (target - current) * 0.3
        
        return new_rhythm
    
    def _should_take_long_pause(
        self, personality: dict, stage_elapsed: float
    ) -> bool:
        """
        【策略3】判断是否应该长停顿
        
        真人的"反直觉停顿"：连续点了几次后突然停一下
        """
        # 冷却检查
        if time.perf_counter() - self.last_long_pause_time < self.long_pause_cooldown:
            return False
        
        # 基于停顿频率
        if random.random() < personality['pause_frequency']:
            # 额外条件：连续点击至少3次后才可能停顿
            if self.click_count_in_stage >= 3:
                return True
        
        return False
    
    def _sample_right_skewed_delay(
        self, center: float, rhythm_range: tuple
    ) -> float:
        """
        右偏分布采样（长尾分布）
        
        真人延迟不是均匀分布，而是右偏（大部分快，偶尔慢）
        使用 Beta 分布模拟
        """
        # 使用 Beta 分布（形状参数 alpha=2, beta=5，右偏）
        # 映射到 rhythm_range
        beta_sample = random.betavariate(2, 5)  # 0-1，右偏
        
        min_rhythm, max_rhythm = rhythm_range
        # 映射到范围，但偏向较小值（右偏）
        delay = min_rhythm + beta_sample * (max_rhythm - min_rhythm)
        
        # 确保在合理范围内
        delay = max(0.1, min(delay, 1.0))
        
        return delay
    
    def should_make_mistake(self) -> bool:
        """
        【策略5】判断是否应该出现小失误
        
        真人的"没必要但真实"的错：已经成功还点一次
        """
        return random.random() < self.stage_personality['mistake_rate']
    
    def on_click_executed(self):
        """点击执行后更新状态"""
        self.click_count_in_stage += 1
    
    def on_stage_changed(self):
        """阶段变化时重置状态"""
        self.stage_start_time = time.perf_counter()
        self.click_count_in_stage = 0
        # 阶段切换时，节奏可能突变（但仍有惯性）
        self.current_rhythm = self.stage_personality['base_rhythm']
        self.rhythm_momentum = 0.0


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
        self.latest_frame: Optional[np.ndarray] = None  # 最新截图帧（完整版，用于调试）
        self.latest_slim_frame: Optional[dict] = None   # 【优化】瘦身版：只包含 detector 需要的行 {y: row_data}
        self.latest_png_data: Optional[bytes] = None    # 最新PNG数据（用于保存截图）
        self.frame_id = 0  # 【修复问题3】帧ID，用于避免空转检测
        self.frame_format = 'BGR'  # 【优化1】帧格式：'BGR'（OpenCV）或'RGBA'（PIL），用于正确读取RGB
        
        # 【优化】预计算每个阶段需要的行（用于瘦身优化）
        self.detector_rows_cache = {}  # {stage_name: set(y坐标)}
        # 【优化3】预编译detectors为(x, y, tr, tg, tb, tol)结构，减少tuple unpack开销
        self.compiled_detectors_cache = {}  # {stage_name: [(x, y, tr, tg, tb, tol), ...]}
        self._precompute_detector_rows()
        
        # 调试相关
        self.debug_screenshot_dir = "temp_screenshots"
        if DEBUG_SAVE_SCREENSHOTS:
            os.makedirs(self.debug_screenshot_dir, exist_ok=True)
        
        # 阶段状态管理
        self.current_stage: Optional[str] = None  # 当前阶段名称（只有detect线程能修改）
        self.stage_lock = threading.Lock()  # 阶段状态锁
        self.stage_executed = set()  # 已执行的阶段（避免重复执行）
        self.stage_action_active = {}  # 阶段动作是否在活跃执行中（用于循环点击）
        self.stage_enter_time = {}  # 阶段进入时间（用于最小驻留时间）
        # 【修复问题4】强制推进事件：改用队列，避免单槽位被覆盖
        self.force_advance_queue = deque()  # [(src_stage, target_stage), ...]
        
        # 【修复问题5】会话级 persona：避免"太稳定地像人"
        self.session_persona = self._generate_session_persona()
        
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
    
    def _generate_session_persona(self) -> dict:
        """
        【修复问题5】生成会话级 persona，避免"太稳定地像人"
        
        每次启动时随机选择一个"人格类型"，然后对基础参数进行缩放
        这样每次运行都像"不同的你"，而不是"永远像同一个情绪稳定的人"
        
        Returns:
            {
                'name': 人格名称,
                'rhythm_scale': 节奏缩放因子 (0.9 ~ 1.1),
                'pause_scale': 停顿频率缩放因子 (0.8 ~ 1.3),
                'mistake_scale': 失误率缩放因子 (0.7 ~ 1.5),
                'tension_scale': 紧张度缩放因子 (0.9 ~ 1.1),
            }
        """
        personas = [
            {
                'name': '冷静型',
                'rhythm_scale': random.uniform(1.0, 1.1),  # 稍慢，更稳定
                'pause_scale': random.uniform(0.8, 1.0),   # 停顿少
                'mistake_scale': random.uniform(0.7, 0.9),  # 失误少
                'tension_scale': random.uniform(0.8, 0.95), # 低紧张
            },
            {
                'name': '手抖型',
                'rhythm_scale': random.uniform(0.9, 1.0),  # 稍快
                'pause_scale': random.uniform(1.1, 1.3),  # 停顿多
                'mistake_scale': random.uniform(1.2, 1.5), # 失误多
                'tension_scale': random.uniform(1.0, 1.1), # 高紧张
            },
            {
                'name': '急躁型',
                'rhythm_scale': random.uniform(0.85, 0.95), # 很快
                'pause_scale': random.uniform(0.7, 0.9),    # 停顿很少
                'mistake_scale': random.uniform(1.0, 1.2),  # 失误稍多
                'tension_scale': random.uniform(1.05, 1.15), # 很高紧张
            },
            {
                'name': '谨慎型',
                'rhythm_scale': random.uniform(1.05, 1.15), # 较慢
                'pause_scale': random.uniform(1.0, 1.2),   # 停顿多（思考）
                'mistake_scale': random.uniform(0.6, 0.8),  # 失误很少
                'tension_scale': random.uniform(0.85, 1.0), # 中等紧张
            },
        ]
        return random.choice(personas)
    
    def update_stats(self, key: str, value: int = 1, stage_name: str = None):
        """更新统计信息（线程安全）"""
        with self.stats_lock:
            if key in self.stats:
                if isinstance(self.stats[key], dict):
                    # 字典类型的统计，需要stage_name参数
                    if stage_name:
                        if stage_name not in self.stats[key]:
                            self.stats[key][stage_name] = 0
                        self.stats[key][stage_name] += value
                else:
                    self.stats[key] += value
    
    def get_stats(self) -> dict:
        """获取统计信息（线程安全，深拷贝）"""
        with self.stats_lock:
            return copy.deepcopy(self.stats)
    
    def _precompute_detector_rows(self):
        """【优化】预计算每个阶段需要的行（用于瘦身优化）+ 预编译detectors"""
        for stage_name, config in STAGE_CONFIGS.items():
            rows = set()
            compiled = []
            for (x, y), target, tol in config.get('detectors', []):
                rows.add(y)
                # 【优化3】预编译为(x, y, tr, tg, tb, tol)结构，减少tuple unpack开销
                tr, tg, tb = target[0], target[1], target[2]
                compiled.append((x, y, tr, tg, tb, tol))
            self.detector_rows_cache[stage_name] = rows
            self.compiled_detectors_cache[stage_name] = compiled
    
    # ---------- 基础工具方法 ----------
    def _tap(self, x: int, y: int):
        """点击坐标（带随机偏移）"""
        offset_x = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
        offset_y = random.randint(-CLICK_COORD_OFFSET, CLICK_COORD_OFFSET)
        self.auto._run_adb_command(['shell', 'input', 'tap', str(x + offset_x), str(y + offset_y)])
    
    def _png_bytes_to_numpy(self, png_data: bytes) -> Tuple[Optional[np.ndarray], str]:
        """
        将 PNG bytes 转换为 numpy array（优化版：优先 OpenCV，直接使用BGR）
        
        Args:
            png_data: PNG 格式的字节数据
            
        Returns:
            (numpy array, format): 
                - OpenCV: (height, width, 3) BGR格式，format='BGR'
                - PIL: (height, width, 4) RGBA格式，format='RGBA'
                - 失败返回 (None, '')
        """
        if not NUMPY_AVAILABLE:
            return None, ''
        
        # 【优化1】优先使用 OpenCV（5-9ms vs PIL 12-25ms，节省 7-16ms）
        # 【优化1】直接使用BGR，不转RGBA（节省2-4ms的cvtColor开销）
        if OPENCV_AVAILABLE:
            try:
                # OpenCV 解码（BGR 格式，直接使用，不转换）
                frame = cv2.imdecode(
                    np.frombuffer(png_data, np.uint8),
                    cv2.IMREAD_COLOR
                )
                if frame is None:
                    return None, ''
                # 【优化1】直接返回BGR，不转RGBA（节省2-4ms）
                return frame, 'BGR'
            except Exception as e:
                # 静默失败，回退到 PIL
                pass
        
        # 回退到 PIL（兼容性）
        if not PIL_AVAILABLE:
            return None, ''
        
        try:
            # 从 bytes 加载图片
            img = Image.open(BytesIO(png_data))
            
            # 转换为 RGBA 模式（确保有 alpha 通道）
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 转换为 numpy array
            frame = np.array(img)
            
            return frame, 'RGBA'
        except Exception as e:
            print(f"❌ PNG 解码失败: {e}")
            return None, ''
    
    def _get_latest_frame(self, slim: bool = True):
        """
        获取最新截图帧（线程安全，优化版：支持瘦身版）
        
        Args:
            slim: 是否返回瘦身版（只包含 detector 需要的行），默认 True
        """
        with self.frame_lock:
            if slim and self.latest_slim_frame is not None:
                # 返回瘦身版（用于检测，减少内存和 cache miss）
                return self.latest_slim_frame
            # 返回完整版（用于调试）
            return self.latest_frame
    
    def debug_check_detection_points(self):
        """
        调试功能：检查所有检测点的实际颜色值
        """
        # 调试时使用完整版 frame
        frame = self._get_latest_frame(slim=False)
        if frame is None:
            print("❌ 没有可用的截图")
            return
        
        print("\n" + "=" * 60)
        print("🔍 检测点颜色调试信息")
        print("=" * 60)
        if isinstance(frame, dict):
            print(f"截图类型: 瘦身版 (只包含需要的行)")
        else:
            print(f"截图尺寸: {frame.shape[1]}x{frame.shape[0]}")
        print()
        
        for stage_name, config in STAGE_CONFIGS.items():
            print(f"📋 阶段: {config['name']} ({stage_name})")
            detectors = config.get('detectors', [])
            
            if not detectors:
                print("  ⚠️ 没有配置检测点")
                print()
                continue
            
            # 【优化1】获取帧格式，用于正确读取RGB
            with self.frame_lock:
                frame_format = self.frame_format
            is_bgr = (frame_format == 'BGR')
            
            for i, ((x, y), target, tol) in enumerate(detectors, 1):
                # 边界检查
                if y >= frame.shape[0] or x >= frame.shape[1]:
                    print(f"  检测点{i}: ({x}, {y}) ❌ 超出截图范围")
                    continue
                
                # 获取实际颜色
                # 【优化1】根据格式正确读取RGB（BGR格式需要反转）
                pixel = frame[y, x]
                if is_bgr:
                    # BGR格式：pixel = [B, G, R]
                    r, g, b = pixel[2], pixel[1], pixel[0]
                else:
                    # RGBA格式：pixel = [R, G, B, A]
                    r, g, b = pixel[0], pixel[1], pixel[2]
                
                # 统一走颜色匹配检测
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
    
    def _detect_stage(self, frame_data, stage_name: str) -> bool:
        """
        检测阶段（优化版：支持瘦身 frame + inline 颜色检测 + 预编译detectors + BGR支持）
        
        Args:
            frame_data: 可以是完整 frame (numpy array) 或瘦身 frame (dict: {y: row_data})
            stage_name: 阶段名称
            
        Returns:
            bool: 是否匹配该阶段
        """
        # 【优化3】使用预编译的detectors（(x, y, tr, tg, tb, tol)结构）
        compiled_detectors = self.compiled_detectors_cache.get(stage_name, [])
        if not compiled_detectors:
            return False
        
        # 判断是完整 frame 还是瘦身 frame
        is_slim = isinstance(frame_data, dict)
        
        # 【优化1】获取帧格式（BGR或RGBA），用于正确读取RGB
        with self.frame_lock:
            frame_format = self.frame_format
        
        # 【优化1】根据格式确定RGB通道索引
        # BGR格式：pixel = [B, G, R]，需要读取pixel[2], pixel[1], pixel[0]
        # RGBA格式：pixel = [R, G, B, A]，需要读取pixel[0], pixel[1], pixel[2]
        is_bgr = (frame_format == 'BGR')
        
        # 【优化3】使用预编译结构，减少tuple unpack开销
        for x, y, tr, tg, tb, tol in compiled_detectors:
            # 获取像素值
            if is_slim:
                # 瘦身版：从 dict 中取行
                if y not in frame_data:
                    if DEBUG_DETECTION_LOG:
                        print(f"⚠️ 检测点行不存在: ({x}, {y})")
                    return False
                row = frame_data[y]
                if x >= row.shape[0]:
                    if DEBUG_DETECTION_LOG:
                        print(f"⚠️ 检测点超出范围: ({x}, {y}), 行宽度: {row.shape[0]}")
                    return False
                pixel = row[x]
            else:
                # 完整版：原有逻辑
                if y >= frame_data.shape[0] or x >= frame_data.shape[1]:
                    if DEBUG_DETECTION_LOG:
                        print(f"⚠️ 检测点超出范围: ({x}, {y}), 截图尺寸: {frame_data.shape[1]}x{frame_data.shape[0]}")
                    return False
                pixel = frame_data[y, x]
            
            # 【优化1】根据格式正确读取RGB（BGR格式需要反转）
            if is_bgr:
                # BGR格式：pixel = [B, G, R]
                r, g, b = pixel[2], pixel[1], pixel[0]
            else:
                # RGBA格式：pixel = [R, G, B, A]
                r, g, b = pixel[0], pixel[1], pixel[2]
            
            # 【优化】inline 颜色检测（避免函数调用开销，节省 1-2ms）
            if not (abs(r - tr) <= tol and abs(g - tg) <= tol and abs(b - tb) <= tol):
                if DEBUG_DETECTION_LOG and DEBUG_MODE:
                    diff = [abs(r - tr), abs(g - tg), abs(b - tb)]
                    max_diff = max(diff)
                    print(f"🔍 [{stage_name}] 点({x},{y}): 实际RGB({r},{g},{b}) vs 目标RGB({tr},{tg},{tb}) "
                          f"容差={tol} 最大差值={max_diff} ❌")
                return False
            elif DEBUG_DETECTION_LOG and DEBUG_MODE:
                diff = [abs(r - tr), abs(g - tg), abs(b - tb)]
                max_diff = max(diff)
                print(f"🔍 [{stage_name}] 点({x},{y}): 实际RGB({r},{g},{b}) vs 目标RGB({tr},{tg},{tb}) "
                      f"容差={tol} 最大差值={max_diff} ✅")

        return True

    def _execute_stage_action(self, stage_name: str):
        """
        执行阶段对应的任务（支持循环点击，带超时控制）
        【修复问题1】action线程不再修改current_stage，只设置force_advance标志
        
        Args:
            stage_name: 阶段名称
        """
        config = STAGE_CONFIGS[stage_name]
        action = config.get('action')
        
        if not action:
            return
        
        action_type = action.get('type')
        
        # 支持循环点击：在阶段内持续点击，直到进入下一阶段或超时
        if action_type == 'click':
            x = action['x']
            y = action['y']
            
            # 【修复问题1】不再在这里写入 stage_action_active，由 detect 线程统一管理
            # detect = 调度者，action = 执行者，职责边界清晰
            
            print(f"🎯 开始执行阶段任务 [{config['name']}]: 循环点击 ({x}, {y})")
            
            # 判断是否为最后阶段
            is_last_stage = (config.get('next_stage') is None)
            
            # 获取期望的下一阶段
            expected_next_stage = config.get('next_stage')
            
            # 循环点击直到进入下一阶段、超时或停止
            click_count = 0
            execution_start = time.perf_counter()
            
            # 【核心改进】创建真人节奏系统（传入会话级 persona）
            rhythm = HumanClickRhythm(stage_name, self.session_persona)
            print(f"🎭 使用节奏人格: {rhythm.stage_personality['name']} "
                  f"(基础节奏: {rhythm.stage_personality['base_rhythm']:.2f}s, "
                  f"紧张度: {rhythm.stage_personality['tension_level']:.1f})")
            
            if is_last_stage:
                # 【修复问题2】最后阶段：执行固定时长后自动停止，同时检测阶段是否消失（完成标志）
                # 使用连续失败次数，避免网络慢/动画过渡等导致的误判
                duration = random.uniform(LAST_STAGE_EXECUTION_DURATION_MIN, LAST_STAGE_EXECUTION_DURATION_MAX)
                print(f"⏱️  最后阶段将执行 {duration:.1f} 秒后自动停止（或连续3次检测失败）")
                
                min_execution_time = LAST_STAGE_EXECUTION_DURATION_MIN * 0.5  # 至少执行一半时间
                fail_count = 0  # 【修复问题2】连续失败次数
                STAGE_DISAPPEAR_THRESHOLD = 3  # 连续失败3次才认为阶段消失
                
                while self.running.is_set():
                    elapsed = time.perf_counter() - execution_start
                    
                    # 检查是否已经进入下一阶段（理论上不应该发生，因为这是最后阶段）
                    with self.stage_lock:
                        current = self.current_stage
                        if current != stage_name:
                            break
                    
                    # 【修复问题2】检测阶段是否消失（使用连续失败次数，避免误判）
                    # 【修复问题5】注意：如果UI有动画fade、按钮disable变灰、半透明overlay等，
                    # 连续3次失败 ≠ 阶段完成。建议后续加"完成信号detector"（如成功toast、页面标题变化等）
                    if elapsed >= min_execution_time:
                        # 检测阶段是否消失需要使用完整版 frame
                        frame = self._get_latest_frame(slim=False)
                        if frame is not None:
                            # 检测阶段是否还存在（如果检测失败，说明页面已变化，可能已完成）
                            still_in_stage = self._detect_stage(frame, stage_name)
                            if not still_in_stage:
                                fail_count += 1
                                if fail_count >= STAGE_DISAPPEAR_THRESHOLD:
                                    print(f"✅ 连续{STAGE_DISAPPEAR_THRESHOLD}次检测失败，阶段已消失，停止点击")
                                    print(f"   💡 提示：如果UI有动画过渡，建议配置'完成信号detector'以提高可靠性")
                                    break
                            else:
                                # 检测成功，重置失败计数
                                fail_count = 0
                    
                    # 检查是否达到最大执行时间
                    if elapsed >= duration:
                        print(f"✅ 最后阶段执行时间到达，自动停止")
                        break
                    
                    # 【修复问题7】检查最大点击次数
                    if click_count >= MAX_CLICKS_PER_STAGE:
                        print(f"⚠️ 达到最大点击次数限制 ({MAX_CLICKS_PER_STAGE})，停止点击")
                        break
                    
                    # 【策略5】小失误模型：偶发重复点击
                    if rhythm.should_make_mistake() and click_count > 0:
                        # 失误：快速再点一次（50-150ms）
                        mistake_delay = random.uniform(0.05, 0.15)
                        time.sleep(mistake_delay)
                        self._tap(x, y)
                        click_count += 1
                        rhythm.on_click_executed()
                        self.update_stats('stage_actions', 1, stage_name)
                        if DEBUG_MODE:
                            print(f"  [失误] 重复点击一次")
                    
                    # 执行点击
                    self._tap(x, y)
                    click_count += 1
                    rhythm.on_click_executed()
                    self.update_stats('stage_actions', 1, stage_name)
                    
                    # 【核心改进】使用真人节奏系统获取延迟
                    # 【修复问题1】不再传入 click_count，完全基于内部状态
                    delay = rhythm.get_next_delay()
                    time.sleep(delay)
            else:
                # 非最后阶段：持续点击，最多STAGE_EXECUTION_TIMEOUT秒，超时后设置推进标志
                print(f"⏱️  非最后阶段将持续点击，最多 {STAGE_EXECUTION_TIMEOUT} 秒后请求推进")
                
                while self.running.is_set():
                    elapsed = time.perf_counter() - execution_start
                    
                    # 检查是否已经进入下一阶段
                    with self.stage_lock:
                        current = self.current_stage
                        if current == expected_next_stage:
                            # 已进入下一阶段，停止点击
                            print(f"✅ 检测到已进入下一阶段，停止当前阶段点击")
                            break
                    
                    # 【修复问题7】检查最大点击次数
                    if click_count >= MAX_CLICKS_PER_STAGE:
                        print(f"⚠️ 达到最大点击次数限制 ({MAX_CLICKS_PER_STAGE})，请求推进到下一阶段")
                        # 【修复问题4】使用队列，避免单槽位被覆盖
                        with self.stage_lock:
                            if expected_next_stage and self.current_stage == stage_name:
                                self.force_advance_queue.append((stage_name, expected_next_stage))
                        break
                    
                    # 检查是否超时
                    if elapsed >= STAGE_EXECUTION_TIMEOUT:
                        print(f"⏱️  执行时间达到 {STAGE_EXECUTION_TIMEOUT} 秒，请求推进到下一阶段")
                        # 【修复问题4】使用队列，避免单槽位被覆盖
                        with self.stage_lock:
                            # 再次确认当前阶段
                            if self.current_stage == stage_name and expected_next_stage:
                                self.force_advance_queue.append((stage_name, expected_next_stage))
                        break
                    
                    # 【策略5】小失误模型：偶发重复点击
                    if rhythm.should_make_mistake() and click_count > 0:
                        # 失误：快速再点一次（50-150ms）
                        mistake_delay = random.uniform(0.05, 0.15)
                        time.sleep(mistake_delay)
                        self._tap(x, y)
                        click_count += 1
                        rhythm.on_click_executed()
                        self.update_stats('stage_actions', 1, stage_name)
                        if DEBUG_MODE:
                            print(f"  [失误] 重复点击一次")
                    
                    # 执行点击
                    self._tap(x, y)
                    click_count += 1
                    rhythm.on_click_executed()
                    self.update_stats('stage_actions', 1, stage_name)
                    
                    # 【核心改进】使用真人节奏系统获取延迟
                    # 【修复问题1】不再传入 click_count，完全基于内部状态
                    delay = rhythm.get_next_delay()
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
                
                # 转换为 numpy array（BGR 或 RGBA 格式）
                frame, frame_format = self._png_bytes_to_numpy(png_data)
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
                
                # 【优化】瘦身：只保留 detector 需要的行（大幅减少内存和 cache miss）
                # 收集所有需要的行
                all_needed_rows = set()
                for rows in self.detector_rows_cache.values():
                    all_needed_rows.update(rows)
                
                # 创建瘦身版 frame：只包含需要的行 {y: row_data}
                # 【修复问题3】改为 copy，避免内存复用导致的竞态（虽然概率极低，但稳妥）
                # 只 copy 几行，成本极低（<0.5ms），换稳定性
                slim_frame = {}
                if all_needed_rows:
                    for y in all_needed_rows:
                        if y < frame.shape[0]:
                            slim_frame[y] = frame[y].copy()  # copy 行数据，避免内存复用竞态
                
                # 更新最新帧和PNG数据（线程安全）
                with self.frame_lock:
                    self.latest_frame = frame  # 完整版（用于调试）
                    self.latest_slim_frame = slim_frame if slim_frame else None  # 瘦身版（用于检测）
                    self.latest_png_data = png_data  # 保存PNG数据用于调试
                    self.frame_format = frame_format  # 【优化1】保存帧格式（BGR或RGBA）
                    self.frame_id += 1  # 【修复问题3】更新帧ID
                
                # 更新统计
                screenshot_count += 1
                with self.stats_lock:
                    self.stats['screenshots'] += 1
                
                # 【修复问题⑤】调试：保存截图（每50张保存一次，降低IO抢占）
                if DEBUG_SAVE_SCREENSHOTS and screenshot_count % 50 == 0:
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
        
        # 【修复问题2+问题⑥】最小驻留时间（秒）
        MIN_STAGE_DURATION = 0.25  # 250ms，保险起见，避免某些App UI更新慢导致的误判
        
        # 【修复问题3】记录上次检测的帧ID，避免空转
        last_frame_id = -1
        
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
                            # 【优化4】自适应sleep：等待到下次截图周期的70%
                            time.sleep(SCREENSHOT_INTERVAL * 0.7)
                            continue
                    
                    # 如果当前阶段为空，只允许检测第一个阶段（stage1）
                    if current is None:
                        # 找到第一个阶段（按STAGE_CONFIGS的顺序）
                        first_stage = list(STAGE_CONFIGS.keys())[0]
                        if stage_name != first_stage:
                            # 【优化4】自适应sleep
                            time.sleep(SCREENSHOT_INTERVAL * 0.7)
                            continue
                    else:
                        # 只允许检测：当前阶段 或 当前阶段的下一阶段
                        expected_next = STAGE_CONFIGS.get(current, {}).get('next_stage')
                        allowed_stages = {current, expected_next}
                        if stage_name not in allowed_stages:
                            # 不在允许范围内，跳过检测
                            # 【优化4】自适应sleep
                            time.sleep(SCREENSHOT_INTERVAL * 0.7)
                            continue
                    
                    # 如果当前已经是这个阶段，跳过检测（避免重复）
                    if current == stage_name:
                        # 【优化4】自适应sleep
                        time.sleep(SCREENSHOT_INTERVAL * 0.7)
                        continue
                
                # 【优化】获取最新截图帧（使用瘦身版）和帧ID（避免空转）
                with self.frame_lock:
                    frame = self.latest_slim_frame  # 使用瘦身版（只包含需要的行）
                    current_frame_id = self.frame_id
                
                if frame is None:
                    # 截图还未就绪，等待
                    # 【优化4】自适应sleep：等待到下次截图周期的70%
                    time.sleep(SCREENSHOT_INTERVAL * 0.7)
                    continue
                
                # 【优化4】自适应检测间隔：如果帧ID没变，sleep更长时间；如果变了，立即检测
                if current_frame_id == last_frame_id:
                    # 帧未更新，sleep到下次截图周期的70%，减少CPU空转和锁竞争
                    time.sleep(SCREENSHOT_INTERVAL * 0.7)
                    continue
                
                # 帧已更新，立即检测（不sleep）
                last_frame_id = current_frame_id
                
                # 【优化】检测阶段（使用瘦身版 frame，减少内存访问）
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
                
                # 【修复问题4】检查是否有action线程请求推进阶段（队列语义，避免覆盖）
                force_advance_event = None
                with self.stage_lock:
                    # 从队列中查找匹配当前阶段的推进请求
                    for i, (src_stage, target_stage) in enumerate(self.force_advance_queue):
                        # 检查是否是当前阶段的推进请求，且目标阶段匹配
                        if src_stage == self.current_stage and target_stage == stage_name:
                            force_advance_event = (src_stage, target_stage)
                            # 移除已处理的请求
                            del self.force_advance_queue[i]
                            break
                
                # 如果有推进请求，优先处理推进
                if force_advance_event:
                    with self.stage_lock:
                        # 再次确认当前阶段
                        if self.current_stage == force_advance_event[0]:
                            src_config = STAGE_CONFIGS.get(force_advance_event[0], {})
                            print(f"🔄 响应推进请求: {src_config.get('name', force_advance_event[0])} -> {config['name']} ({stage_name})")
                            self.current_stage = stage_name
                            self.stage_enter_time[stage_name] = time.perf_counter()
                            
                            # 更新统计
                            self.update_stats('stage_detections', 1, stage_name)
                            
                            # 【修复问题1+问题①】统一使用 stage_executed 作为唯一判断，消除竞态窗口
                            if stage_name not in self.stage_executed:
                                self.stage_executed.add(stage_name)
                                action_thread = threading.Thread(
                                    target=self._execute_stage_action,
                                    args=(stage_name,),
                                    daemon=True
                                )
                                action_thread.start()
                                self.stage_action_active[stage_name] = True
                
                # 正常检测流程
                if detected:
                    with self.stage_lock:
                        # 双重检查：再次确认阶段门禁（防止并发问题）
                        current = self.current_stage
                        
                        # 再次检查最小驻留时间
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
                            
                            # 【修复问题1】只有detect线程能修改current_stage（单一真相源）
                            self.current_stage = stage_name
                            self.stage_enter_time[stage_name] = time.perf_counter()
                            
                            # 更新统计
                            self.update_stats('stage_detections', 1, stage_name)
                            
                            # 【修复问题1+问题①】统一使用 stage_executed 作为唯一判断，消除竞态窗口
                            if stage_name not in self.stage_executed:
                                self.stage_executed.add(stage_name)
                                action_thread = threading.Thread(
                                    target=self._execute_stage_action,
                                    args=(stage_name,),
                                    daemon=True
                                )
                                action_thread.start()
                                self.stage_action_active[stage_name] = True
                
                # 【优化4】自适应sleep：如果帧未更新，sleep更长时间；如果已更新，立即检测
                # 这里在循环末尾，如果帧已更新则立即继续（不sleep），否则sleep
                # 注意：帧ID检查在上面已经处理，这里只是兜底
                time.sleep(SCREENSHOT_INTERVAL * 0.7)
                
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
            frame = self._get_latest_frame(slim=False)
            if frame is not None and not isinstance(frame, dict):
                print(f"✅ 截图已就绪 (尺寸: {frame.shape[1]}x{frame.shape[0]})")
                # 【修复问题5】调试：只在启动时检查一次检测点颜色（性能优化）
                if DEBUG_MODE and DEBUG_CHECK_ONCE:
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
                            # 最后一个阶段，等待执行完成（2-5秒）
                            print(f"\n⏳ 已到达最后阶段，等待执行完成...")
                            time.sleep(LAST_STAGE_EXECUTION_DURATION_MAX + 1.0)
                            print(f"✅ 已完成所有阶段，当前在: {config['name']}")
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
