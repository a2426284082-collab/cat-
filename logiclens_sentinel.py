import time
import threading
import pyperclip
from pynput import keyboard, mouse

# ==========================================
# 核心组件 0 (模拟态): 全局开关状态
# ==========================================
IS_TOGGLE_ON = True  # True代表小球为绿色，False代表红色禁用
ctrl_pressed = False

# ==========================================
# 核心组件 1: 输入哨兵 (Input Sentinel)
# ==========================================

def on_press(key):
    """监听键盘按下：标记 Ctrl 状态"""
    global ctrl_pressed
    # 兼容左Ctrl和右Ctrl
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        ctrl_pressed = True

def on_release(key):
    """监听键盘松开：取消 Ctrl 状态"""
    global ctrl_pressed
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        ctrl_pressed = False

def trigger_extraction():
    """核心物理动作：模拟复制并提取内容"""
    print("[LogicLens 哨兵] 捕获意图：Ctrl + 左键释放。正在提取...")
    
    # 1. 预清空剪贴板，防止读到上一次的旧数据
    pyperclip.copy("")
    
    # 2. 模拟物理按键：Ctrl + C
    ctrl_controller = keyboard.Controller()
    with ctrl_controller.pressed(keyboard.Key.ctrl):
        ctrl_controller.press('c')
        ctrl_controller.release('c')
        
    # 3. 极短的系统 IO 延迟，确保操作系统把数据放进剪贴板
    time.sleep(0.1)
    
    # 4. 获取剪贴板数据
    selected_code = pyperclip.paste()
    
    if selected_code.strip():
        print("\n" + "="*40)
        print("🎯 成功提取到代码片段：")
        print(selected_code)
        print("="*40 + "\n")
        # ⚠️ 未来对接点：这里将会把 selected_code 传递给【组件 2: AST聚合器】
    else:
        print("[LogicLens 哨兵] 提取为空，可能是未划选任何文本。")

def on_click(x, y, button, pressed):
    """监听鼠标点击动作"""
    # 如果开关关闭，哨兵直接休眠，零干扰
    if not IS_TOGGLE_ON:
        return

    # 逻辑判定门：必须是鼠标左键，且是【释放瞬间】(pressed == False)
    if button == mouse.Button.left and not pressed:
        # 且此时 Ctrl 键必须处于按住状态
        if ctrl_pressed:
            # 开启独立线程去执行复制动作，防止阻塞全局鼠标监听导致系统卡顿
            threading.Thread(target=trigger_extraction).start()

def start_sentinel():
    """启动哨兵进程"""
    print("🟢 LogicLens 输入哨兵已启动！")
    print("👉 测试方法：在任意编辑器或网页中，按住 [Ctrl] 键，用鼠标划选一段文字并松开左键。")
    print("按 Ctrl+C 终止终端运行。\n")

    # 启动双通道监听：键盘与鼠标
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    mouse_listener = mouse.Listener(on_click=on_click)

    keyboard_listener.start()
    mouse_listener.start()

    keyboard_listener.join()
    mouse_listener.join()

if __name__ == "__main__":
    start_sentinel()