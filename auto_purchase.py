"""
自动依次点击商品详情页面的按钮
1. 选择规格 - 单个盲盒随机发货
2. 购买方式 - 送到家
3. 底部确认按钮（到货通知/立即购买）
"""
from adb_automation import ADBAutomation
import time
import subprocess
import threading
import queue
from typing import Optional, Tuple

# ======== 坐标配置：请根据自己手机实际坐标修改 ========
# 详情页底部「确定」按钮的中心坐标（1080x2280 屏幕）
# 从截图看，这是一个大的黑色按钮，位于屏幕底部中央
DETAIL_BOTTOM_X = 540
DETAIL_BOTTOM_Y = 1965

# 支付页面底部「确认信息并支付」按钮的中心坐标（1080x2280 屏幕）
# 从截图看，这个按钮在底部操作栏的右侧
PAY_BUTTON_X = 900  # 右侧按钮，大约在屏幕右侧
PAY_BUTTON_Y = 2070  # 底部操作栏高度

# 支付页弹框中「确认无误」按钮的中心坐标（1080x2280 屏幕）
# 根据最新截图，按钮在弹框底部居中，略高于底部操作栏
POPUP_CONFIRM_X = 540  # 居中
POPUP_CONFIRM_Y = 1450  # 调低到弹框内按钮位置附近（可根据实际微调）
# ===============================================================


def auto_click_purchase_buttons():
    """自动依次点击购买相关按钮"""
    start_time = time.time()  # 记录开始时间
    
    auto = ADBAutomation()
    
    if not auto.connect():
        print("❌ 设备连接失败")
        return False
    
    print("\n" + "=" * 60)
    print("开始自动点击购买流程")
    print("=" * 60)
    
    # 坐标配置（基于 1080x2280 屏幕）
    coordinates = {
        "单个盲盒随机发货": (222, 904),   # bounds="[45,855][399,954]"
        "送到家": (139, 1198),            # bounds="[45,1149][234,1248]"
        "底部确认按钮": (791, 1965)       # bounds="[549,1896][1032,2034]" (右侧按钮)
    }
    
    # 步骤1: 点击"单个盲盒随机发货"
    print("\n📌 步骤 1/3: 点击'单个盲盒随机发货'")
    x, y = coordinates["单个盲盒随机发货"]
    # 极速模式：不额外等待，由 ADB 自身耗时决定
    if auto.tap(x, y, delay=0):
        print(f"   ✅ 已点击: ({x}, {y})")
    else:
        print("   ❌ 点击失败")
        return False
    
    # 步骤2: 点击"送到家"
    print("\n📌 步骤 2/3: 点击'送到家'")
    x, y = coordinates["送到家"]
    if auto.tap(x, y, delay=0):
        print(f"   ✅ 已点击: ({x}, {y})")
    else:
        print("   ❌ 点击失败")
        return False
    
    # 步骤3: 点击底部确认按钮（可能是"到货通知"或"立即购买"）
    print("\n📌 步骤 3/3: 点击底部确认按钮")
    x, y = coordinates["底部确认按钮"]
    if auto.tap(x, y, delay=0):
        print(f"   ✅ 已点击: ({x}, {y})")
    else:
        print("   ❌ 点击失败")
        return False
    
    # 计算总耗时
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "=" * 60)
    print("✅ 所有步骤完成！")
    print(f"⏱️  总耗时: {total_time:.2f} 秒")
    print("=" * 60)
    return True


def auto_click_with_fallback():
    """
    自动点击，带备用方案
    如果底部只有一个确认按钮（居中），使用备用坐标
    """
    start_time = time.time()  # 记录开始时间
    
    auto = ADBAutomation()
    
    if not auto.connect():
        print("❌ 设备连接失败")
        return False
    
    print("\n" + "=" * 60)
    print("开始自动点击购买流程（带备用方案）")
    print("=" * 60)
    
    # 坐标配置
    coordinates = {
        "单个盲盒随机发货": (222, 904),
        "送到家": (139, 1198),
        "底部确认按钮_右侧": (791, 1965),  # 双按钮时的右侧按钮
        "底部确认按钮_居中": (540, 1965),   # 单按钮时可能居中
    }
    
    # 步骤1: 点击"单个盲盒随机发货"
    print("\n📌 步骤 1/3: 点击'单个盲盒随机发货'")
    x, y = coordinates["单个盲盒随机发货"]
    if not auto.tap(x, y, delay=0):
        return False
    
    # 步骤2: 点击"送到家"
    print("\n📌 步骤 2/3: 点击'送到家'")
    x, y = coordinates["送到家"]
    if not auto.tap(x, y, delay=0):
        return False
    
    # 步骤3: 尝试点击底部按钮（先试右侧，再试居中）
    print("\n📌 步骤 3/3: 点击底部确认按钮")
    
    # 优先尝试右侧按钮（双按钮场景）
    x, y = coordinates["底部确认按钮_右侧"]
    print(f"   尝试右侧按钮: ({x}, {y})")
    if auto.tap(x, y, delay=0):
        print("   ✅ 使用右侧按钮成功")
        # 计算总耗时
        end_time = time.time()
        total_time = end_time - start_time
        print("\n" + "=" * 60)
        print("✅ 所有步骤完成！")
        print(f"⏱️  总耗时: {total_time:.2f} 秒")
        print("=" * 60)
        return True
    
    # 如果右侧失败，尝试居中按钮（单按钮场景）
    print("   右侧按钮失败，尝试居中按钮...")
    x, y = coordinates["底部确认按钮_居中"]
    if auto.tap(x, y, delay=0):
        print(f"   ✅ 使用居中按钮成功: ({x}, {y})")
        # 计算总耗时
        end_time = time.time()
        total_time = end_time - start_time
        print("\n" + "=" * 60)
        print("✅ 所有步骤完成！")
        print(f"⏱️  总耗时: {total_time:.2f} 秒")
        print("=" * 60)
        return True
    else:
        print("   ❌ 所有备用方案都失败")
        # 即使失败也记录耗时
        end_time = time.time()
        total_time = end_time - start_time
        print(f"\n⏱️  失败前耗时: {total_time:.2f} 秒")
        return False


def _pick_first_authorized_device(adb_path: str) -> Optional[str]:
    """
    极速选设备：只挑 status == 'device' 的真机，跳过 unauthorized/offline。
    返回 UDID 或 None
    """
    try:
        result = subprocess.run(
            [adb_path, "devices"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split("\n")[1:]  # skip header
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            udid, status = parts[0], parts[1]
            # 只接受已授权在线设备
            if status == "device" and not udid.startswith("127.0.0.1"):
                return udid
        return None
    except Exception:
        return None


def click_bottom_confirm_only(
    prefer_right: bool = True,
    fast_async: bool = False,
    fallback_center: bool = True,
    gap_ms: int = 0,
) -> bool:
    """
    进入页面后，仅点击底部按钮（右侧按钮 / 居中确认）。

    - prefer_right: 先尝试右侧按钮（双按钮场景）
    - fast_async: True 时使用 Popen 异步下发 tap（脚本返回更快，但无法确认是否点中）
    - fallback_center: 右侧失败后是否尝试居中按钮
    - gap_ms: 异步模式下两次点击间隔（毫秒）
    """
    start = time.perf_counter()

    auto = ADBAutomation()
    if not auto.adb_path:
        print("❌ 未找到 ADB")
        return False

    # 不走 auto.connect()（它会额外取屏幕尺寸、打印等），这里只做最小化选设备
    if not auto.device_udid:
        udid = _pick_first_authorized_device(auto.adb_path)
        if not udid:
            print("❌ 未找到已授权的在线设备（device 状态）")
            print("   请先在手机上点“允许 USB 调试”，或执行 `adb devices` 确认状态为 device")
            return False
        auto.device_udid = udid

    # 坐标（1080x2280，底部按钮区域）
    right_xy = (791, 1965)   # 右侧按钮（到货通知/立即购买）
    center_xy = (540, 1965)  # 单按钮“确认”大概率居中

    first_xy = right_xy if prefer_right else center_xy
    second_xy = center_xy if prefer_right else right_xy

    def _do_tap(x: int, y: int) -> bool:
        if fast_async:
            auto.fast_tap(x, y)
            return True3
        return auto.tap(x, y, delay=0)

    ok = _do_tap(*first_xy)
    if ok:
        elapsed = (time.perf_counter() - start) * 1000
        mode = "async" if fast_async else "sync"
        print(f"✅ 已点击底部按钮({first_xy[0]}, {first_xy[1]}) | 模式={mode} | 耗时={elapsed:.1f}ms")
        return True

    # 同步模式下才能知道失败并 fallback；异步模式默认不做 fallback（避免误点两次）
    if (not fast_async) and fallback_center:
        ok2 = _do_tap(*second_xy)
        elapsed = (time.perf_counter() - start) * 1000
        if ok2:
            print(f"✅ 右侧失败后已点击备用按钮({second_xy[0]}, {second_xy[1]}) | 耗时={elapsed:.1f}ms")
            return True
        print(f"❌ 两个底部按钮坐标都点击失败 | 耗时={elapsed:.1f}ms")
        return False

    # 异步模式可选间隔后再下发第二次（默认关闭）
    if fast_async and fallback_center:
        if gap_ms > 0:
            time.sleep(gap_ms / 1000.0)
        _do_tap(*second_xy)
        elapsed = (time.perf_counter() - start) * 1000
        print(
            f"✅ 已异步下发两次点击: {first_xy} -> {second_xy} | 间隔={gap_ms}ms | 耗时={elapsed:.1f}ms（仅脚本下发耗时）"
        )
        return True

    elapsed = (time.perf_counter() - start) * 1000
    print(f"❌ 点击失败 | 耗时={elapsed:.1f}ms")
    return False


def rush_with_refresh(
    duration_sec: float = 90.0,
    cycle_interval: float = 0.4,
    click_gap_ms: int = 80,
    pay_gap_ms: int = 80,
    enable_pay_click: bool = True,
) -> None:
    """
    抢购专用：在详情页内循环【下拉刷新 + 极速点击底部按钮】。

    Args:
        duration_sec: 抢购总时长（秒），到时间后自动停止
        cycle_interval: 每一轮“刷新+点击”目标周期（秒）
        click_gap_ms: 右侧按钮与居中按钮之间的点击间隔（毫秒，0 表示紧挨着点两次）
    """
    auto = ADBAutomation()
    if not auto.connect():
        print("❌ 设备连接失败，无法开始抢购循环")
        return

    right_xy = (791, 1965)   # 右侧按钮（到货通知/立即购买）
    center_xy = (540, 1965)  # 居中确认
    pay_xy = (PAY_BUTTON_X, PAY_BUTTON_Y)  # 支付页面底部「确认信息并支付」

    print("\n" + "=" * 60)
    print("🚀 开始抢购循环：下拉刷新 + 点击底部按钮 + 支付页确认按钮")
    print(f"目标总时长: {duration_sec:.1f}s, 每轮周期: {cycle_interval:.3f}s")
    print(f"商品页按钮间隔: {click_gap_ms}ms, 支付按钮间隔: {pay_gap_ms}ms, 支付按钮点击: {enable_pay_click}")
    print("提示：请提前进入商品详情页，脚本运行期间不要手动操作该页面。")
    print("=" * 60)

    start = time.perf_counter()
    cycle_count = 0

    try:
        while True:
            now = time.perf_counter()
            if now - start >= duration_sec:
                break

            cycle_start = now
            cycle_count += 1

            # 1) 快速下拉刷新（异步）
            auto.fast_swipe_refresh()

            # 2) 等待一小会儿让接口返回 & UI 更新
            time.sleep(0.12)  # 可按网络情况微调：0.1~0.3 之间

            # 3) 商品详情页底部按钮：先右侧，再居中（两次都发，保证尽可能命中）
            auto.fast_tap(*right_xy)
            if click_gap_ms > 0:
                time.sleep(click_gap_ms / 1000.0)
            auto.fast_tap(*center_xy)

            # 4) 支付页底部按钮：无论当前是否已经跳转，都会顺带点一下
            #    - 在详情页时，这个坐标通常落在空白区域，不会有副作用
            #    - 一旦页面切到支付页，就会命中「确认信息并支付」
            if enable_pay_click:
                if pay_gap_ms > 0:
                    time.sleep(pay_gap_ms / 1000.0)
                auto.fast_tap(*pay_xy)

            # 5) 控制整体节奏，使一轮接近 cycle_interval
            elapsed_cycle = time.perf_counter() - cycle_start
            if cycle_interval > 0 and elapsed_cycle < cycle_interval:
                time.sleep(cycle_interval - elapsed_cycle)

            # 简单统计输出（每 1s 左右打印一次）
            if cycle_count % int(max(1, 1 / max(cycle_interval, 0.1))) == 0:
                elapsed = time.perf_counter() - start
                print(
                    f"⏱️ 已运行 {elapsed:.1f}s, 轮次: {cycle_count}, "
                    f"平均 {cycle_count / max(elapsed, 0.1):.1f} 轮/秒"
                )

    except KeyboardInterrupt:
        print("\n⏹️ 手动停止抢购循环")

    total = time.perf_counter() - start
    print("\n" + "=" * 60)
    print(f"✅ 抢购循环结束，总耗时: {total:.1f}s, 总轮次: {cycle_count}")
    print("=" * 60)


def one_shot_detail_pay_flow(
    wait_to_pay: float = 0.15,
    wait_to_popup: float = 0.15,
) -> bool:
    """
    一次性完成：
    1. 详情页：点击底部「确定」按钮
    2. 支付页：点击底部最右侧「确认信息并支付」
    3. 弹框：点击弹框里的「确认无误」按钮

    使用前请先：
      - 在详情页停好，再运行本函数
      - 根据自己手机调好 DETAIL_BOTTOM_* / PAY_BUTTON_* / POPUP_CONFIRM_* 坐标
    """
    start = time.perf_counter()

    auto = ADBAutomation()
    if not auto.connect():
        print("❌ 设备连接失败")
        return False

    print("\n" + "=" * 60)
    print("开始一次性流程：详情页 -> 支付页 -> 弹框确认")
    print("=" * 60)

    # 1) 详情页：点击底部「确定」按钮
    print(f"📌 步骤 1/3: 详情页底部「确定」按钮 ({DETAIL_BOTTOM_X}, {DETAIL_BOTTOM_Y})")
    if not auto.tap(DETAIL_BOTTOM_X, DETAIL_BOTTOM_Y, delay=0):
        print("   ❌ 详情页底部点击失败")
        return False

    # 给页面一点时间跳转到支付页（极速模式：减少等待）
    time.sleep(wait_to_pay)

    # 2) 支付页：点击底部最右侧「确认信息并支付」
    #    这一步会触发弹框出现
    print(f"📌 步骤 2/3: 支付页底部「确认信息并支付」 ({PAY_BUTTON_X}, {PAY_BUTTON_Y})")
    if not auto.tap(PAY_BUTTON_X, PAY_BUTTON_Y, delay=0):
        print("   ❌ 支付页底部按钮点击失败，跳过弹框点击")
        return False

    # 等待弹框出现（弹框只有在点击「确认信息并支付」后才会显示）
    time.sleep(wait_to_popup)

    # 3) 弹框：点击「确认无误」（如果已配置坐标）
    #    注意：这个按钮只有在步骤2点击「确认信息并支付」后才会出现
    if POPUP_CONFIRM_X > 0 and POPUP_CONFIRM_Y > 0:
        print(f"📌 步骤 3/3: 弹框「确认无误」按钮 ({POPUP_CONFIRM_X}, {POPUP_CONFIRM_Y})")
        print("   ℹ️  弹框已出现（由步骤2触发），点击确认按钮")
        if not auto.tap(POPUP_CONFIRM_X, POPUP_CONFIRM_Y, delay=0):
            print("   ❌ 弹框确认按钮点击失败")
            return False
    else:
        print("📌 步骤 3/3: 跳过弹框确认（未配置 POPUP_CONFIRM_X/Y 坐标）")

    total = time.perf_counter() - start
    print("\n" + "=" * 60)
    print(f"✅ 一次性流程完成，总耗时: {total*1000:.1f}ms")
    print("=" * 60)
    return True


def ultra_fast_purchase_flow(
    wait_to_pay: float = 0.1,
    wait_to_popup: float = 0.15,
) -> bool:
    """
    极速版本：使用异步 fast_tap 实现最快速度的连续点击
    
    流程：
    1. 详情页：点击底部「确定」按钮 -> 跳转到支付页
    2. 支付页：点击底部最右侧「确认信息并支付」-> 触发弹框
    3. 弹框：点击弹框里的「确认无误」按钮（仅在点击支付按钮后执行）
    
    注意：
    - 弹框只有在点击「确认信息并支付」后才会出现
    - 使用 fast_tap（异步）无法确认是否点中，但速度最快
    """
    start = time.perf_counter()

    auto = ADBAutomation()
    if not auto.adb_path:
        print("❌ 未找到 ADB")
        return False

    # 极速模式：不走 connect()，只做最小化选设备
    if not auto.device_udid:
        udid = _pick_first_authorized_device(auto.adb_path)
        if not udid:
            print("❌ 未找到已授权的在线设备（device 状态）")
            return False
        auto.device_udid = udid

    print("\n" + "=" * 60)
    print("🚀 极速模式：异步连续点击（最快速度）")
    print("=" * 60)

    # 1) 详情页：点击底部「确定」按钮（异步）
    print(f"📌 步骤 1/3: 详情页底部「确定」({DETAIL_BOTTOM_X}, {DETAIL_BOTTOM_Y}) [异步]")
    auto.fast_tap(DETAIL_BOTTOM_X, DETAIL_BOTTOM_Y)

    # 等待页面跳转到支付页
    time.sleep(wait_to_pay)

    # 2) 支付页：点击底部最右侧「确认信息并支付」（同步，确保点击成功）
    #    这一步会触发弹框出现
    print(f"📌 步骤 2/3: 支付页「确认信息并支付」({PAY_BUTTON_X}, {PAY_BUTTON_Y}) [同步]")
    if not auto.tap(PAY_BUTTON_X, PAY_BUTTON_Y, delay=0):
        print("   ❌ 支付页按钮点击失败，跳过弹框点击")
        return False

    # 等待弹框出现（弹框只有在点击「确认信息并支付」后才会显示）
    time.sleep(wait_to_popup)

    # 3) 弹框：点击「确认无误」（异步）
    #    注意：这个按钮只有在步骤2点击「确认信息并支付」后才会出现
    if POPUP_CONFIRM_X > 0 and POPUP_CONFIRM_Y > 0:
        print(f"📌 步骤 3/3: 弹框「确认无误」({POPUP_CONFIRM_X}, {POPUP_CONFIRM_Y}) [异步]")
        print("   ℹ️  弹框已出现（由步骤2触发），点击确认按钮")
        auto.fast_tap(POPUP_CONFIRM_X, POPUP_CONFIRM_Y)
    else:
        print("📌 步骤 3/3: 跳过弹框确认（未配置 POPUP_CONFIRM_X/Y 坐标）")

    total = time.perf_counter() - start
    print("\n" + "=" * 60)
    print(f"✅ 极速流程完成，脚本耗时: {total*1000:.1f}ms")
    print("⚠️  注意：步骤1和3使用异步模式，实际点击可能仍在执行中")
    print("=" * 60)
    return True


def detect_text_in_ui_hierarchy(auto: ADBAutomation, target_text: str, timeout: float = 10.0, check_interval: float = 0.2) -> bool:
    """
    通过 UI 层次结构检测指定文本是否出现
    
    Args:
        auto: ADBAutomation 实例
        target_text: 要检测的文本（如"确认信息并支付"、"确认无误"）
        timeout: 超时时间（秒）
        check_interval: 检测间隔（秒）
    
    Returns:
        是否检测到文本
    """
    start = time.perf_counter()
    
    while time.perf_counter() - start < timeout:
        try:
            # 获取 UI 层次结构到临时文件
            temp_file = '/sdcard/temp_ui_check.xml'
            success, msg = auto._run_adb_command(['shell', 'uiautomator', 'dump', temp_file])
            
            if success:
                # 拉取到本地临时文件
                local_temp = 'temp_ui_check.xml'
                success2, msg2 = auto._run_adb_command(['pull', temp_file, local_temp])
                
                if success2:
                    # 读取文件内容，检测目标文本
                    try:
                        with open(local_temp, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if target_text in content:
                                # 清理临时文件
                                import os
                                try:
                                    os.remove(local_temp)
                                    auto._run_adb_command(['shell', 'rm', temp_file])
                                except:
                                    pass
                                return True
                    except Exception:
                        pass
                    
                    # 清理临时文件
                    import os
                    try:
                        os.remove(local_temp)
                    except:
                        pass
        except Exception:
            pass
        
        time.sleep(check_interval)
    
    return False


def smart_sync_click_flow(
    wait_detail_to_pay: float = 0.5,
    detect_pay_timeout: float = 5.0,
    detect_popup_timeout: float = 3.0,
    check_interval: float = 0.15,
) -> bool:
    """
    智能同步点击流程：通过 UI 层次结构检测页面状态，在合适的时机点击
    
    流程：
    1. 点击详情页「确定」按钮
    2. 循环检测支付页是否出现（检测"确认信息并支付"文字）
    3. 一旦检测到支付页，立即点击「确认信息并支付」按钮
    4. 循环检测弹框是否出现（检测"确认无误"文字）
    5. 一旦检测到弹框，立即点击「确认无误」按钮
    
    Args:
        wait_detail_to_pay: 点击详情页按钮后，等待多久开始检测支付页（秒）
        detect_pay_timeout: 检测支付页的超时时间（秒）
        detect_popup_timeout: 检测弹框的超时时间（秒）
        check_interval: UI 层次结构检测间隔（秒），越小检测越频繁但可能影响性能
    """
    start = time.perf_counter()
    
    auto = ADBAutomation()
    if not auto.connect():
        print("❌ 设备连接失败")
        return False
    
    print("\n" + "=" * 60)
    print("🧠 智能同步点击流程：通过 UI 检测页面状态")
    print("=" * 60)
    
    # 步骤1: 点击详情页「确定」按钮
    print(f"📌 步骤 1/3: 点击详情页「确定」按钮 ({DETAIL_BOTTOM_X}, {DETAIL_BOTTOM_Y})")
    if not auto.tap(DETAIL_BOTTOM_X, DETAIL_BOTTOM_Y, delay=0):
        print("   ❌ 详情页按钮点击失败")
        return False
    
    print(f"   ✅ 已点击，等待 {wait_detail_to_pay:.2f}s 后开始检测支付页...")
    time.sleep(wait_detail_to_pay)
    
    # 步骤2: 检测支付页是否出现，然后点击
    print(f"\n📌 步骤 2/3: 检测支付页「确认信息并支付」按钮是否出现...")
    print(f"   检测超时: {detect_pay_timeout:.1f}s, 检测间隔: {check_interval*1000:.0f}ms")
    
    pay_detected = detect_text_in_ui_hierarchy(
        auto, 
        "确认信息并支付", 
        timeout=detect_pay_timeout,
        check_interval=check_interval
    )
    
    if pay_detected:
        print(f"   ✅ 检测到支付页！立即点击「确认信息并支付」({PAY_BUTTON_X}, {PAY_BUTTON_Y})")
        if not auto.tap(PAY_BUTTON_X, PAY_BUTTON_Y, delay=0):
            print("   ❌ 支付页按钮点击失败")
            return False
    else:
        print(f"   ⚠️  超时未检测到支付页，尝试直接点击支付页按钮...")
        if not auto.tap(PAY_BUTTON_X, PAY_BUTTON_Y, delay=0):
            print("   ❌ 支付页按钮点击失败")
            return False
    
    # 步骤3: 检测弹框是否出现，然后点击
    print(f"\n📌 步骤 3/3: 检测弹框「确认无误」按钮是否出现...")
    print(f"   检测超时: {detect_popup_timeout:.1f}s, 检测间隔: {check_interval*1000:.0f}ms")
    
    popup_detected = detect_text_in_ui_hierarchy(
        auto,
        "确认无误",
        timeout=detect_popup_timeout,
        check_interval=check_interval
    )
    
    if popup_detected:
        print(f"   ✅ 检测到弹框！立即点击「确认无误」({POPUP_CONFIRM_X}, {POPUP_CONFIRM_Y})")
        if POPUP_CONFIRM_X > 0 and POPUP_CONFIRM_Y > 0:
            if not auto.tap(POPUP_CONFIRM_X, POPUP_CONFIRM_Y, delay=0):
                print("   ❌ 弹框按钮点击失败")
                return False
        else:
            print("   ⚠️  弹框坐标未配置，跳过")
    else:
        print(f"   ⚠️  超时未检测到弹框")
        if POPUP_CONFIRM_X > 0 and POPUP_CONFIRM_Y > 0:
            print(f"   尝试直接点击弹框按钮 ({POPUP_CONFIRM_X}, {POPUP_CONFIRM_Y})...")
            auto.tap(POPUP_CONFIRM_X, POPUP_CONFIRM_Y, delay=0)
        else:
            print("   ⚠️  弹框坐标未配置，跳过")
    
    total = time.perf_counter() - start
    print("\n" + "=" * 60)
    print(f"✅ 智能同步流程完成，总耗时: {total:.2f}s")
    print("=" * 60)
    return True


def staged_manual_advance_flow(
    stage_duration_sec: float = 20.0,
    click_interval_sec: float = 0.05,
) -> None:
    """
    人工推进的分阶段点击（适合微信小程序无法自动识别页面跳转的场景）

    - 每个阶段默认循环点击 20 秒（可配）
    - 你在手机上看到页面已经跳转时，在控制台按回车（或输入任意字符回车），即可立刻进入下一阶段
    - 输入 q 回车：立即退出
    - 第三阶段点击「确认无误」后，如果你看到页面已跳转，再按一次回车即可结束整个程序并输出统计

    阶段定义：
    1) 详情页：循环点底部「确定」
    2) 支付页：循环点「确认信息并支付」
    3) 弹框：循环点「确认无误」
    """
    auto = ADBAutomation()
    if not auto.connect():
        print("❌ 设备连接失败")
        return

    stages = [
        ("阶段1-详情页「确定」", (DETAIL_BOTTOM_X, DETAIL_BOTTOM_Y)),
        ("阶段2-支付页「确认信息并支付」", (PAY_BUTTON_X, PAY_BUTTON_Y)),
        ("阶段3-弹框「确认无误」", (POPUP_CONFIRM_X, POPUP_CONFIRM_Y)),
    ]

    # 过滤掉未配置的弹框坐标（避免误点 (0,0)）
    filtered_stages = []
    for name, (x, y) in stages:
        if x <= 0 or y <= 0:
            if "弹框" in name:
                continue
        filtered_stages.append((name, (x, y)))
    stages = filtered_stages

    # Windows 下：把 input() 放到子线程经常会直接 EOF，导致误触发退出。
    # 这里优先用 msvcrt 读取按键：回车推进、q 退出（不会莫名其妙退出）。
    use_msvcrt = False
    try:
        import msvcrt  # type: ignore
        use_msvcrt = True
    except Exception:
        use_msvcrt = False

    cmd_q: "queue.Queue[str]" = queue.Queue()

    if not use_msvcrt:
        def input_worker():
            while True:
                try:
                    s = input()
                    # input() 读到空行也要推进阶段，所以不要 strip 掉空行
                    cmd_q.put(s.rstrip("\n"))
                except EOFError:
                    # stdin 不可用：不要自动退出，改为只靠阶段超时推进
                    cmd_q.put("__EOF__")
                    return
                except Exception:
                    cmd_q.put("__EOF__")
                    return

        threading.Thread(target=input_worker, daemon=True).start()

    print("\n" + "=" * 60)
    print("🧭 人工推进模式：每阶段循环点击，手动输入推进下一阶段")
    print("=" * 60)
    print(f"每阶段默认时长: {stage_duration_sec:.1f}s | 点击间隔: {click_interval_sec*1000:.0f}ms")
    print("操作：")
    print("- 按 n → 进入下一阶段（无需回车）")
    print("- 按 q → 退出")
    print("- 第三阶段点完「确认无误」后：看到页面跳转，再按 n 结束程序并输出统计")
    print("=" * 60)

    stage_idx = 0
    start_all = time.perf_counter()
    stage_stats = []  # [{name, seconds, clicks}]

    while stage_idx < len(stages):
        stage_name, (x, y) = stages[stage_idx]
        print(f"\n▶ {stage_name} 开始：循环点击 ({x}, {y})")
        print(f"  你可以随时输入任意字符推进下一阶段；或输入 q 退出。")

        stage_start = time.perf_counter()
        click_count = 0

        while True:
            # 检查是否收到控制台指令
            cmd = None
            if use_msvcrt:
                # q 退出；回车推进；其他任意键也推进
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getwch()
                        # Windows 下更稳的操作：按 n 进入下一阶段；按 q 退出
                        if ch.lower() == "q":
                            cmd = "q"
                        elif ch.lower() == "n":
                            cmd = "__NEXT__"
                        else:
                            cmd = None
                except Exception:
                    cmd = None
            else:
                try:
                    cmd = cmd_q.get_nowait()
                except queue.Empty:
                    cmd = None

            if cmd is not None:
                if isinstance(cmd, str) and cmd == "__EOF__":
                    # stdin 不可用：不再响应手动输入，只靠超时推进
                    cmd = None
                else:
                    if isinstance(cmd, str) and cmd.lower() == "q":
                        total = time.perf_counter() - start_all
                        print(f"\n⏹️ 已退出（总耗时 {total:.1f}s）")
                        return

                    # 手动推进：只有收到 n 才推进（避免误触）
                    if isinstance(cmd, str) and cmd != "__NEXT__":
                        cmd = None
                    if cmd is None:
                        # 继续循环点击
                        pass
                    else:
                        stage_elapsed = time.perf_counter() - stage_start
                        stage_stats.append({"name": stage_name, "seconds": stage_elapsed, "clicks": click_count})
                        print(f"✅ 收到 n：进入下一阶段（本阶段耗时 {stage_elapsed:.2f}s，点击 {click_count} 次）")
                        stage_idx += 1
                        break

            # 超时自动进入下一阶段
            if time.perf_counter() - stage_start >= stage_duration_sec:
                stage_elapsed = time.perf_counter() - stage_start
                stage_stats.append({"name": stage_name, "seconds": stage_elapsed, "clicks": click_count})
                print(f"⏱️ 阶段超时 {stage_duration_sec:.1f}s，自动进入下一阶段（本阶段耗时 {stage_elapsed:.2f}s，点击 {click_count} 次）")
                stage_idx += 1
                break

            # 同步点击（可控、可观察）
            auto.tap(x, y, delay=0)
            click_count += 1

            # 如果是弹框阶段，为了更保险，在垂直方向多点一次（覆盖按钮上下浮动）
            if "弹框" in stage_name and POPUP_CONFIRM_X > 0 and POPUP_CONFIRM_Y > 0:
                auto.tap(POPUP_CONFIRM_X, POPUP_CONFIRM_Y + 80, delay=0)
                click_count += 1

            if click_interval_sec > 0:
                time.sleep(click_interval_sec)

    # 阶段全部跑完后：等待用户确认“已跳转”再退出（尤其是弹框确认后）
    print("\n" + "=" * 60)
    print("✅ 已完成所有阶段的点击。")
    print("如果你看到页面已经跳转/流程结束：请再按一次回车结束程序；或输入 q 回车退出。")
    print("=" * 60)

    if use_msvcrt:
        # 等待 n 或 q
        while True:
            try:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch.lower() in ("q", "n"):
                        break
            except Exception:
                break
            time.sleep(0.05)
    else:
        while True:
            cmd = cmd_q.get()  # 阻塞等待输入
            if isinstance(cmd, str) and (cmd.lower() == "q" or cmd == ""):
                break
            if cmd == "__EOF__":
                break
            # 任意输入也视为结束
            break

    total = time.perf_counter() - start_all
    print("\n" + "=" * 60)
    print("📊 阶段耗时统计：")
    for st in stage_stats:
        print(f"- {st['name']}: {st['seconds']:.2f}s, 点击 {st['clicks']} 次")
    print(f"✅ 程序结束（总耗时 {total:.2f}s）")
    print("=" * 60)


def concurrent_click_three_positions(
    click_interval: float = 0.05,
    stats_interval: float = 1.0,
) -> None:
    """
    并发点击三个位置，持续循环直到手动停止（Ctrl+C）
    
    三个位置：
    1. 详情页底部「确定」按钮
    2. 支付页「确认信息并支付」按钮
    3. 弹框「确认无误」按钮
    
    无论当前在哪个页面，都会同时点击这三个位置，确保快速响应。
    
    Args:
        click_interval: 每次点击之间的间隔（秒），越小越快，但可能影响稳定性
        stats_interval: 统计信息输出间隔（秒）
    """
    auto = ADBAutomation()
    if not auto.adb_path:
        print("❌ 未找到 ADB")
        return

    # 极速模式：不走 connect()，只做最小化选设备
    if not auto.device_udid:
        udid = _pick_first_authorized_device(auto.adb_path)
        if not udid:
            print("❌ 未找到已授权的在线设备（device 状态）")
            return
        auto.device_udid = udid

    # 三个位置的坐标
    positions = [
        ("详情页「确定」", DETAIL_BOTTOM_X, DETAIL_BOTTOM_Y),
        ("支付页「确认信息并支付」", PAY_BUTTON_X, PAY_BUTTON_Y),
        ("弹框「确认无误」", POPUP_CONFIRM_X, POPUP_CONFIRM_Y) if (POPUP_CONFIRM_X > 0 and POPUP_CONFIRM_Y > 0) else None,
    ]
    # 过滤掉未配置的坐标
    positions = [p for p in positions if p is not None]

    if not positions:
        print("❌ 没有配置任何有效坐标")
        return

    print("\n" + "=" * 60)
    print("🚀 并发点击模式：三个位置同时高频点击")
    print("=" * 60)
    print(f"点击位置：")
    for name, x, y in positions:
        print(f"  - {name}: ({x}, {y})")
    print(f"点击间隔: {click_interval*1000:.1f}ms")
    print("提示：按 Ctrl+C 停止")
    print("=" * 60)

    start_time = time.perf_counter()
    click_count = 0
    last_stats_time = start_time
    running = True

    def click_worker():
        """工作线程：持续点击所有位置"""
        nonlocal click_count
        while running:
            # 并发点击所有位置
            for name, x, y in positions:
                auto.fast_tap(x, y)
            click_count += len(positions)
            
            # 控制点击频率
            if click_interval > 0:
                time.sleep(click_interval)

    try:
        # 启动点击线程
        worker_thread = threading.Thread(target=click_worker, daemon=True)
        worker_thread.start()

        # 主线程：显示统计信息
        while running:
            time.sleep(stats_interval)
            
            elapsed = time.perf_counter() - start_time
            current_count = click_count
            clicks_per_sec = current_count / elapsed if elapsed > 0 else 0
            
            print(
                f"⏱️  已运行: {elapsed:.1f}s | "
                f"总点击: {current_count} 次 | "
                f"平均速度: {clicks_per_sec:.1f} 次/秒"
            )

    except KeyboardInterrupt:
        print("\n⏹️  收到停止信号，正在停止...")
        running = False
        
        # 等待工作线程结束
        worker_thread.join(timeout=1.0)
        
        total = time.perf_counter() - start_time
        print("\n" + "=" * 60)
        print(f"✅ 并发点击已停止")
        print(f"📊 总运行时间: {total:.1f}s")
        print(f"📊 总点击次数: {click_count} 次")
        print(f"📊 平均速度: {click_count / total:.1f} 次/秒" if total > 0 else "📊 平均速度: 0 次/秒")
        print("=" * 60)


if __name__ == "__main__":
    # 使用基础版本
    # auto_click_purchase_buttons()
    
    # 或使用带备用方案的版本（推荐）
    # auto_click_with_fallback()

    # 极速：只点底部按钮
    # click_bottom_confirm_only(prefer_right=True, fast_async=False, fallback_center=True)

    # 抢购模式：循环 下拉刷新 + 极速点击底部按钮
    # rush_with_refresh(duration_sec=90.0, cycle_interval=0.4, click_gap_ms=80)

    # 一次性流程：详情页底部 -> 支付页确认信息并支付 -> 弹框确认（同步模式，可确认是否点中）
    # one_shot_detail_pay_flow(wait_to_pay=0.15, wait_to_popup=0.15)

    # 极速模式：异步连续点击（最快速度，推荐用于抢购）
    # ultra_fast_purchase_flow(wait_to_pay=0.1, wait_to_popup=0.1)

    # 人工推进模式：每阶段默认循环20秒，你看到页面跳转后在控制台输入任意字符推进下一阶段
    staged_manual_advance_flow(stage_duration_sec=20.0, click_interval_sec=0.05)

    # 并发点击模式：三个位置同时高频点击，持续循环直到手动停止（备选方案）
    # concurrent_click_three_positions(click_interval=0.05, stats_interval=1.0)

