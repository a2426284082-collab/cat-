import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QPainter, QColor

# ==========================================
# 核心组件 4: 沉浸式阅读器 (Explanation Bubble)
# ==========================================
class ExplanationBubble(QWidget):
    def __init__(self, text: str, x: int, y: int):
        super().__init__()
        
        # 物理逻辑：无边框、置顶、作为工具窗口（不在任务栏显示图标）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        # 背景透明，为了实现圆角阴影效果
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 布局设置
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # 标签渲染：承载大模型返回的大白话
        self.label = QLabel(text)
        self.label.setWordWrap(True) # 允许自动换行
        self.label.setFont(QFont("Microsoft YaHei", 10))
        
        # 极简暗黑风 CSS 样式
        self.label.setStyleSheet("""
            QLabel {
                color: #E0E0E0;
                background-color: rgba(30, 30, 30, 240);
                border: 1px solid #555555;
                border-radius: 12px;
                padding: 18px;
                line-height: 1.5;
            }
        """)
        
        # 设置最大宽度，防止文字太长撑满屏幕
        self.label.setMaximumWidth(450)
        layout.addWidget(self.label)
        
        # 根据内容自动调整大小，并移动到鼠标附近位置
        self.adjustSize()
        
        # 防止气泡超出屏幕边界的微调（假设简单右下角偏移）
        offset_x, offset_y = 15, 15
        self.move(x + offset_x, y + offset_y)

    def keyPressEvent(self, event):
        """物理直觉：按 ESC 键瞬间销毁窗口"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def focusOutEvent(self, event):
        """物理直觉：鼠标点击其他地方，气泡自动消失"""
        self.close()


# ==========================================
# 核心组件 0: 状态指示器与全局开关 (Floating Ball)
# ==========================================
class FloatingBall(QWidget):
    def __init__(self):
        super().__init__()
        # 物理逻辑：无边框、置顶、工具窗口
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.is_active = True # True 为绿色监听，False 为红色休眠
        self.drag_pos = QPoint()
        
        # 初始化球体大小和位置
        self.resize(24, 24)
        self.move(50, 50)
        self.setToolTip("LogicLens 开关\n双击：切换状态\n拖拽：移动位置")

    def paintEvent(self, event):
        """绘制极简的小球"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # 抗锯齿，边缘平滑
        
        # 绿色代表工作中，红色代表休眠
        color = QColor(46, 204, 113, 200) if self.is_active else QColor(231, 76, 60, 200)
        
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

    def mousePressEvent(self, event):
        """记录拖拽起点"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """实现任意拖拽逻辑"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + diff)
            self.drag_pos = event.globalPosition().toPoint()

    def mouseDoubleClickEvent(self, event):
        """架构师防呆设计：用双击切换状态，防止与拖拽冲突"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_active = not self.is_active
            print(f"[UI 层] 状态切换 -> {'🟢 监听中' if self.is_active else '🔴 已休眠'}")
            self.update() # 触发重新绘制颜色

# ==========================================
# 本地测试与推演演示
# ==========================================
if __name__ == "__main__":
    # 需要提前安装: pip install PyQt6
    app = QApplication(sys.argv)
    
    print("🟢 正在启动 UI 界面层...")
    print("👉 尝试拖拽绿色小球，或双击它切换状态。")
    
    # 1. 启动悬浮小球
    ball = FloatingBall()
    ball.show()
    
    # 2. 模拟触发：直接在屏幕 (300, 300) 的位置弹出一个翻译气泡
    mock_translation = (
        "🎯 AI 架构师透视结果：\n\n"
        "- [文件IO]：打开本地路径读取视频文件二进制数据。\n"
        "- [算力消耗]：将视频内容进行 MD5 哈希运算提取指纹。\n"
        "- [业务校验]：查询内存数据库是否存在该指纹，存在则拦截，不存在则放行。"
    )
    
    # 弹出一个气泡示例
    bubble = ExplanationBubble(mock_translation, 300, 300)
    bubble.show()
    
    # 强制获取焦点，以便测试 ESC 秒关功能
    bubble.activateWindow()
    bubble.setFocus()
    
    sys.exit(app.exec())