import sys
import os
import json
import time
import ast
import requests
import threading
import pyperclip
import traceback

# 尝试导入高级渲染库
try:
    import markdown
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
    HAS_RICH_RENDER = True
except ImportError:
    HAS_RICH_RENDER = False

# 强制重定向标准输出，防止在 pythonw 模式下报错
if sys.executable.endswith("pythonw.exe"):
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

try:
    from pynput import keyboard, mouse
    from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                                 QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QPushButton, QMessageBox,
                                 QComboBox, QGroupBox, QFormLayout, QInputDialog, QTextBrowser,
                                 QSplitter, QMenu, QFileDialog) 
    from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QObject, QRect, QSize, QRegularExpression
    from PyQt6.QtGui import (QFont, QPainter, QColor, QRadialGradient, 
                             QSyntaxHighlighter, QTextCharFormat, QTextFormat)
except ImportError as e:
    with open("error_log.txt", "w", encoding="utf-8") as f:
        f.write(f"启动失败：库未安装。\n请运行: pip install pynput pyperclip PyQt6 requests\n具体错误: {str(e)}")
    sys.exit(1)

# ==========================================
# 本地配置存储
# ==========================================
CONFIG_FILE = "logiclens_config.json"
DEFAULT_CONFIG = {
    "current_api_index": 0,
    "api_configs": [
        {
            "name": "DeepSeek 官方",
            "api_url": "https://api.deepseek.com/chat/completions",
            "api_model": "deepseek-chat",
            "api_key": ""
        }
    ],
    "current_prompt_index": 0,
    "prompts": [
        {"name": "极简架构师", "content": "你是一个极致冷酷的逻辑透视机。请用最简练的大白话输出逻辑意图。禁止解释基础语法。"},
        {"name": "详细导师", "content": "请用温和易懂的语言，详细解释代码的业务逻辑、实现思路及底层原理，按点列出。"},
        {"name": "找 Bug 专家", "content": "请分析代码片段中潜在的隐患、性能瓶颈、错误和边界条件遗漏。"}
    ]
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config.update(saved)
                if "api_configs" not in saved:
                    config["api_configs"] = [{
                        "name": "默认节点 (旧版迁移)",
                        "api_url": saved.get("api_url", "https://api.deepseek.com/chat/completions"),
                        "api_model": saved.get("api_model", "deepseek-chat"),
                        "api_key": saved.get("api_key", "")
                    }]
                    config["current_api_index"] = 0
                if "prompts" not in saved:
                    config["prompts"] = [
                        {"name": "默认提示词", "content": saved.get("system_prompt", DEFAULT_CONFIG["prompts"][0]["content"])}
                    ]
                    config["current_prompt_index"] = 0
        except: pass
    return config

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)


# ==========================================
# 🌟 实时语法高亮解析器 (用于左侧编辑器)
# ==========================================
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        def create_format(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold: f.setFontWeight(QFont.Weight.Bold)
            if italic: f.setFontItalic(True)
            return f

        # VSCode One Dark Pro 像素级复刻方案
        formats = {
            "keyword": create_format("#C678DD", bold=True),  # 紫色：关键字
            "string": create_format("#98C379"),              # 绿色：字符串
            "comment": create_format("#7F848E", italic=True),# 灰色：注释 (倾斜)
            "number": create_format("#D19A66"),              # 橙色：数字
            "function": create_format("#61AFEF"),            # 蓝色：函数类名
            "builtin": create_format("#E5C07B"),             # 黄色：内置函数
            "decorator": create_format("#E5C07B"),           # 黄色：装饰器
        }

        # 1. 关键字
        keywords = ["and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif", "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while", "with", "yield"]
        for word in keywords:
            self.highlightingRules.append((QRegularExpression(rf"\b{word}\b"), formats["keyword"]))

        # 2. 内置函数
        builtins = ["print", "len", "range", "open", "int", "str", "float", "list", "dict", "set", "tuple", "type", "super", "self"]
        for word in builtins:
            self.highlightingRules.append((QRegularExpression(rf"\b{word}\b"), formats["builtin"]))

        # 3. 数字
        self.highlightingRules.append((QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?\b"), formats["number"]))

        # 4. 装饰器
        self.highlightingRules.append((QRegularExpression(r"@[a-zA-Z_0-9.]+"), formats["decorator"]))

        # 5. 字符串
        self.highlightingRules.append((QRegularExpression(r'".*?"'), formats["string"]))
        self.highlightingRules.append((QRegularExpression(r"'.*?'"), formats["string"]))

        # 6. 注释 (必须放在最后以覆盖其他规则)
        self.highlightingRules.append((QRegularExpression(r"#[^\n]*"), formats["comment"]))

        self.funcFormat = formats["function"]

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
        
        # 函数和类名二次解析提取
        func_pattern = QRegularExpression(r"\b(?:def|class)\s+([a-zA-Z_0-9_]+)")
        it = func_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(1), match.capturedLength(1), self.funcFormat)

# ==========================================
# 🌟 带行号的 IDE 级真实代码编辑器 (用于左侧)
# ==========================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    file_dropped = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        
        font = QFont("Consolas", 11)
        self.setFont(font)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: none;
            }
        """)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # 挂载实时高亮引擎
        self.highlighter = PythonHighlighter(self.document())
        self.setAcceptDrops(True)

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num /= 10
            digits += 1
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#2A2D32") # 当前行高亮颜色
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#1E1E1E"))
        painter.setPen(QColor("#3E4451"))
        painter.drawLine(event.rect().topRight(), event.rect().bottomRight())

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#5C6370"))
                painter.setFont(self.font())
                painter.drawText(0, top, self.lineNumberArea.width() - 8, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoomIn(1)
            else:
                self.zoomOut(1)
            self.updateLineNumberAreaWidth(0)
        else:
            super().wheelEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 🚀 【重大修正区】: 提升安全阅览上限，防止日常 Python 脚本被强行截断
                    # 原来是 15000（约15KB，甚至装不下500行代码）。
                    # 现在调整为 5,000,000（约 5MB，可轻松容纳 10万行 代码），既能保障日常流畅，又可完美防呆。
                    MAX_SAFE_LENGTH = 5000000 
                    if len(content) > MAX_SAFE_LENGTH:
                        content = content[:MAX_SAFE_LENGTH] + "\n... [内容极长，已被系统自动截断以防止超大非代码文件引发界面崩溃] ..."
                    
                    self.file_dropped.emit(content, file_path)
                except Exception: pass
            event.acceptProposedAction()

# ==========================================
# 🌟 AI 结果浏览器 (支持无极缩放与富文本渲染)
# ==========================================
class ZoomDropBrowser(QTextBrowser):
    file_dropped = pyqtSignal(str, str) 
    def __init__(self, placeholder_text=""):
        super().__init__()
        self.setAcceptDrops(True)
        self.setReadOnly(True) 
        self.setPlaceholderText(placeholder_text)
        self.setFont(QFont("Consolas", 11))
        self.setStyleSheet("QTextBrowser { background-color: #1E1E1E; color: #D4D4D4; border: none; }")

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0: self.zoomIn(1)
            else: self.zoomOut(1)
        else: super().wheelEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f: 
                        content = f.read()
                    
                    # 🚀 同步主编辑器的安全限流设计
                    MAX_SAFE_LENGTH = 5000000
                    if len(content) > MAX_SAFE_LENGTH:
                        content = content[:MAX_SAFE_LENGTH] + "\n... [内容极长，已被系统自动截断] ..."
                        
                    self.file_dropped.emit(content, file_path)
                except Exception: pass
            event.acceptProposedAction()


# ==========================================
# GUI 组件: 主控面板 (大看板模式)
# ==========================================
class ControlPanel(QWidget):
    config_updated_signal = pyqtSignal(dict)
    ai_file_dropped_signal = pyqtSignal(str)

    def __init__(self, current_config):
        super().__init__()
        self.setWindowTitle("LogicLens 代码大看板")
        self.resize(1100, 650) 
        self.current_config = current_config
        self.current_left_file_path = None 
        
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        
        # --- 上半部分：设置区 (默认折叠) ---
        self.settings_widget = QWidget()
        layout = QVBoxLayout(self.settings_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        api_group = QGroupBox("🔌 API 节点设置")
        api_main_layout = QVBoxLayout()
        api_combo_layout = QHBoxLayout()
        self.api_combo = QComboBox()
        self.api_combo.currentIndexChanged.connect(self.on_api_change)
        api_combo_layout.addWidget(QLabel("选择节点:"))
        api_combo_layout.addWidget(self.api_combo, 1)
        
        add_api_btn = QPushButton("➕")
        add_api_btn.setFixedWidth(40)
        add_api_btn.clicked.connect(self.add_api)
        api_combo_layout.addWidget(add_api_btn)
        
        del_api_btn = QPushButton("🗑️")
        del_api_btn.setFixedWidth(40)
        del_api_btn.clicked.connect(self.del_api)
        api_combo_layout.addWidget(del_api_btn)
        api_main_layout.addLayout(api_combo_layout)
        
        api_form = QFormLayout()
        self.url_in = QLineEdit()
        self.model_in = QLineEdit()
        self.key_in = QLineEdit()
        self.key_in.setEchoMode(QLineEdit.EchoMode.Password)
        api_form.addRow("API 地址:", self.url_in)
        api_form.addRow("模型名称:", self.model_in)
        api_form.addRow("API 密钥:", self.key_in)
        
        api_main_layout.addLayout(api_form)
        save_api_btn = QPushButton("💾 仅保存当前 API 配置")
        save_api_btn.setStyleSheet("background-color: #2E86C1; color: white; padding: 5px; border-radius: 4px;")
        save_api_btn.clicked.connect(self.save_api_settings)
        api_main_layout.addWidget(save_api_btn)
        api_group.setLayout(api_main_layout)
        layout.addWidget(api_group)
        
        prompt_group = QGroupBox("🎭 提示词配置")
        p_layout = QVBoxLayout()
        h_layout = QHBoxLayout()
        self.p_combo = QComboBox()
        self.p_combo.currentIndexChanged.connect(self.on_p_change)
        h_layout.addWidget(QLabel("选择人设:"))
        h_layout.addWidget(self.p_combo, 1)
        
        add_p_btn = QPushButton("➕")
        add_p_btn.setFixedWidth(40)
        add_p_btn.clicked.connect(self.add_p)
        h_layout.addWidget(add_p_btn)
        
        del_p_btn = QPushButton("🗑️")
        del_p_btn.setFixedWidth(40)
        del_p_btn.clicked.connect(self.del_p)
        h_layout.addWidget(del_p_btn)
        p_layout.addLayout(h_layout)
        self.p_edit = QTextEdit()
        self.p_edit.setMaximumHeight(80)
        p_layout.addWidget(self.p_edit)

        save_prompt_btn = QPushButton("💾 仅保存当前提示词")
        save_prompt_btn.setStyleSheet("background-color: #27AE60; color: white; padding: 5px; border-radius: 4px;")
        save_prompt_btn.clicked.connect(self.save_prompt_settings)
        p_layout.addWidget(save_prompt_btn)
        prompt_group.setLayout(p_layout)
        layout.addWidget(prompt_group)
        
        self.refresh_api_ui()
        self.refresh_p_ui()
        
        btn_layout = QHBoxLayout()
        self.hide_btn = QPushButton("🔽 最小化控制台")
        self.hide_btn.clicked.connect(self.hide)
        
        if not HAS_RICH_RENDER:
            warn_lbl = QLabel("⚠️ 未安装 pygments/markdown，代码高亮未开启")
            warn_lbl.setStyleSheet("color: #E74C3C; font-size: 8pt;")
            btn_layout.addWidget(warn_lbl)
            
        btn_layout.addStretch()
        btn_layout.addWidget(self.hide_btn)
        layout.addLayout(btn_layout)
        splitter.addWidget(self.settings_widget)
        
        # --- 下半部分：左右分屏大看板区 ---
        board_widget = QWidget()
        board_layout = QVBoxLayout(board_widget)
        board_layout.setContentsMargins(0, 5, 0, 0)
        
        top_control_layout = QHBoxLayout()
        top_control_layout.setContentsMargins(5, 5, 5, 10)
        btn_style = "padding: 6px 14px; color: #E0E0E0; background-color: #3E3E42; border-radius: 4px; font-weight: bold;"
        
        self.immersive_btn = QPushButton("⚙️ 设置配置")
        self.immersive_btn.setStyleSheet("padding: 6px 14px; color: #FFF; background-color: #007ACC; border-radius: 4px; font-weight: bold;")
        self.immersive_btn.clicked.connect(self.toggle_immersive)
        top_control_layout.addWidget(self.immersive_btn)
        
        self.pin_btn = QPushButton("📌 窗口置顶")
        self.pin_btn.setStyleSheet(btn_style)
        self.pin_btn.clicked.connect(self.toggle_pin)
        top_control_layout.addWidget(self.pin_btn)
        
        self.toggle_left_btn = QPushButton("👁️ 收起左侧")
        self.toggle_left_btn.setStyleSheet(btn_style)
        self.toggle_left_btn.clicked.connect(self.toggle_left_panel)
        top_control_layout.addWidget(self.toggle_left_btn)
        
        self.toggle_right_btn = QPushButton("🧠 收起 AI")
        self.toggle_right_btn.setStyleSheet(btn_style)
        self.toggle_right_btn.clicked.connect(self.toggle_right_panel)
        top_control_layout.addWidget(self.toggle_right_btn)
        
        top_control_layout.addStretch()
        
        self.quick_save_btn = QPushButton("💾 保存到原目录")
        self.quick_save_btn.setStyleSheet("padding: 6px 14px; color: #FFF; background-color: #D35400; border-radius: 4px; font-weight: bold;")
        self.quick_save_btn.clicked.connect(self.save_to_original)
        top_control_layout.addWidget(self.quick_save_btn)
        
        self.save_code_btn = QPushButton("📁 另存为...")
        self.save_code_btn.setStyleSheet("padding: 6px 14px; color: #FFF; background-color: #27AE60; border-radius: 4px; font-weight: bold;")
        self.save_code_btn.clicked.connect(self.save_as_new)
        top_control_layout.addWidget(self.save_code_btn)
        
        clear_btn = QPushButton("🗑️ 清空右侧面板")
        clear_btn.setStyleSheet(btn_style)
        clear_btn.clicked.connect(self.clear_all_boards)
        top_control_layout.addWidget(clear_btn)
        
        board_layout.addLayout(top_control_layout)
        kanban_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ====================================
        # 左侧：纯净阅读与真实编辑区
        # ====================================
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_header = QHBoxLayout()
        left_lbl = QLabel("📜 本地代码库 (完美语法高亮 / 行号标尺 / Ctrl+Z撤销)")
        left_lbl.setStyleSheet("color: #888; font-weight: bold; margin-bottom: 5px;")
        left_header.addWidget(left_lbl)
        left_header.addStretch()
        
        # 增加撤销/重做实体按钮
        undo_btn = QPushButton("↩️ 撤回")
        undo_btn.setStyleSheet("padding: 2px 8px; background-color: #333; color: #E0E0E0; border-radius: 4px;")
        undo_btn.clicked.connect(lambda: self.pure_code_view.undo())
        left_header.addWidget(undo_btn)
        
        redo_btn = QPushButton("↪️ 重做")
        redo_btn.setStyleSheet("padding: 2px 8px; background-color: #333; color: #E0E0E0; border-radius: 4px;")
        redo_btn.clicked.connect(lambda: self.pure_code_view.redo())
        left_header.addWidget(redo_btn)
        
        left_layout.addLayout(left_header)
        
        # 挂载真实的带行号代码编辑器
        self.pure_code_view = CodeEditor()
        self.pure_code_view.setPlaceholderText("这里是一个全功能的代码编辑器！\n1. 可以直接敲代码或 Ctrl+V 粘贴（即刻获得高亮与行号）。\n2. 拖入本地文件可自动读取。\n3. 支持 Ctrl+Z 撤销，Ctrl+Y 重做。\n4. 支持 Ctrl+滚轮 无极缩放。")
        self.pure_code_view.file_dropped.connect(self.handle_pure_code_drop)
        left_layout.addWidget(self.pure_code_view)
        
        # ====================================
        # 右侧：AI 解析区
        # ====================================
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_lbl = QLabel("🧠 AI 架构透视区 (划选代码将触发深度解析)")
        right_lbl.setStyleSheet("color: #C678DD; font-weight: bold; margin-bottom: 5px;")
        right_layout.addWidget(right_lbl)
        
        self.ai_view = ZoomDropBrowser("将文件拖拽至此，或按住 Ctrl+左键划选任意代码片段，即可召唤大模型透视逻辑。")
        self.ai_view.file_dropped.connect(lambda content, path: self.ai_file_dropped_signal.emit(content))
        right_layout.addWidget(self.ai_view)
        
        kanban_splitter.addWidget(self.left_panel)
        kanban_splitter.addWidget(self.right_panel)
        kanban_splitter.setSizes([550, 550]) 
        
        board_layout.addWidget(kanban_splitter)
        splitter.addWidget(board_widget)
        
        self.settings_widget.hide()

    def toggle_pin(self):
        is_on_top = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if is_on_top:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self.pin_btn.setText("📌 窗口置顶")
            self.pin_btn.setStyleSheet("padding: 6px 14px; color: #E0E0E0; background-color: #3E3E42; border-radius: 4px; font-weight: bold;")
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.pin_btn.setText("📍 取消置顶")
            self.pin_btn.setStyleSheet("padding: 6px 14px; color: #FFF; background-color: #E74C3C; border-radius: 4px; font-weight: bold;")
        self.show()

    def save_to_original(self):
        content = self.pure_code_view.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "空画板", "左侧画板里没有代码哦！")
            return
            
        default_path = self.current_left_file_path if self.current_left_file_path else ""
        file_path, _ = QFileDialog.getSaveFileName(self, "保存到原目录", default_path, "Python Files (*.py);;Text Files (*.txt);;All Files (*)")
        if file_path:
            self._write_file(file_path, content)

    def save_as_new(self):
        content = self.pure_code_view.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "空画板", "左侧画板里没有代码哦！")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "另存为新文件", "", "Python Files (*.py);;Text Files (*.txt);;All Files (*)")
        if file_path:
            self._write_file(file_path, content)
            
    def _write_file(self, file_path, content):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.current_left_file_path = file_path 
            QMessageBox.information(self, "成功", f"代码已成功保存至:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"发生了未知错误:\n{str(e)}")

    def toggle_left_panel(self):
        if self.left_panel.isVisible():
            self.left_panel.hide()
            self.toggle_left_btn.setText("👁️ 展开左侧")
        else:
            self.left_panel.show()
            self.toggle_left_btn.setText("👁️ 收起左侧")

    def toggle_right_panel(self):
        if self.right_panel.isVisible():
            self.right_panel.hide()
            self.toggle_right_btn.setText("🧠 展开 AI")
        else:
            self.right_panel.show()
            self.toggle_right_btn.setText("🧠 收起 AI")

    def clear_all_boards(self):
        self.ai_view.clear()

    def toggle_immersive(self):
        if self.settings_widget.isVisible():
            self.settings_widget.hide()
            self.immersive_btn.setText("⚙️ 设置配置")
            self.immersive_btn.setStyleSheet("padding: 6px 14px; color: #FFF; background-color: #007ACC; border-radius: 4px; font-weight: bold;")
        else:
            self.settings_widget.show()
            self.immersive_btn.setText("🔲 收起设置")
            self.immersive_btn.setStyleSheet("padding: 6px 14px; color: #E0E0E0; background-color: #3E3E42; border-radius: 4px; font-weight: bold;")

    # --- API 管理复用 ---
    def refresh_api_ui(self):
        self.api_combo.blockSignals(True)
        self.api_combo.clear()
        for ac in self.current_config["api_configs"]: self.api_combo.addItem(ac["name"])
        idx = self.current_config["current_api_index"]
        self.api_combo.setCurrentIndex(idx)
        ac = self.current_config["api_configs"][idx]
        self.url_in.setText(ac.get("api_url", ""))
        self.model_in.setText(ac.get("api_model", ""))
        self.key_in.setText(ac.get("api_key", ""))
        self.api_combo.blockSignals(False)

    def on_api_change(self, i):
        if i >= 0:
            self.current_config["current_api_index"] = i
            ac = self.current_config["api_configs"][i]
            self.url_in.setText(ac.get("api_url", ""))
            self.model_in.setText(ac.get("api_model", ""))
            self.key_in.setText(ac.get("api_key", ""))

    def add_api(self):
        name, ok = QInputDialog.getText(self, "新增 API 节点", "名称:")
        if ok and name.strip():
            self.save_api_settings_silent()
            self.current_config["api_configs"].append({"name": name.strip(), "api_url": "", "api_model": "", "api_key": ""})
            self.current_config["current_api_index"] = len(self.current_config["api_configs"]) - 1
            self.refresh_api_ui()

    def del_api(self):
        if len(self.current_config["api_configs"]) > 1:
            del self.current_config["api_configs"][self.api_combo.currentIndex()]
            self.current_config["current_api_index"] = 0
            self.refresh_api_ui()

    def refresh_p_ui(self):
        self.p_combo.blockSignals(True)
        self.p_combo.clear()
        for p in self.current_config["prompts"]: self.p_combo.addItem(p["name"])
        idx = self.current_config["current_prompt_index"]
        self.p_combo.setCurrentIndex(idx)
        self.p_edit.setText(self.current_config["prompts"][idx]["content"])
        self.p_combo.blockSignals(False)

    def on_p_change(self, i):
        if i >= 0:
            self.current_config["current_prompt_index"] = i
            self.p_edit.setText(self.current_config["prompts"][i]["content"])

    def add_p(self):
        name, ok = QInputDialog.getText(self, "新增", "人设名称:")
        if ok and name.strip():
            self.save_prompt_settings_silent()
            self.current_config["prompts"].append({"name": name.strip(), "content": ""})
            self.current_config["current_prompt_index"] = len(self.current_config["prompts"]) - 1
            self.refresh_p_ui()

    def del_p(self):
        if len(self.current_config["prompts"]) > 1:
            del self.current_config["prompts"][self.p_combo.currentIndex()]
            self.current_config["current_prompt_index"] = 0
            self.refresh_p_ui()

    def save_api_settings_silent(self):
        idx_api = self.api_combo.currentIndex()
        if idx_api >= 0:
            self.current_config["api_configs"][idx_api]["api_url"] = self.url_in.text().strip()
            self.current_config["api_configs"][idx_api]["api_model"] = self.model_in.text().strip()
            self.current_config["api_configs"][idx_api]["api_key"] = self.key_in.text().strip()

    def save_prompt_settings_silent(self):
        idx_p = self.p_combo.currentIndex()
        if idx_p >= 0:
            self.current_config["prompts"][idx_p]["content"] = self.p_edit.toPlainText().strip()

    def save_api_settings(self):
        self.save_api_settings_silent()
        save_config(self.current_config)
        self.config_updated_signal.emit(self.current_config)

    def save_prompt_settings(self):
        self.save_prompt_settings_silent()
        save_config(self.current_config)
        self.config_updated_signal.emit(self.current_config)

    # 🌟 右侧 AI 画板使用 Pygments，全面对齐左侧真实编辑器的 One Dark Pro 配色
    def generate_html_block(self, code, translation=None):
        ts = time.strftime("%H:%M:%S")
        highlighted_code = ""
        
        if HAS_RICH_RENDER:
            custom_css = """
            <style>
                .custom-kanban { background-color: #1E1E1E; padding: 10px; border-radius: 8px; line-height: 1.5; }
                .custom-kanban .linenos { color: #5C6370; background-color: #1E1E1E; padding-right: 12px; margin-right: 12px; border-right: 1px solid #3E4451; user-select: none; }
                
                /* 修复高亮规则：完全符合程序员的直觉 */
                .custom-kanban .c, .custom-kanban .c1, .custom-kanban .cm, .custom-kanban .ch, .custom-kanban .cp, .custom-kanban .cs { color: #7F848E; font-style: italic; } /* 注释：高级灰 */
                .custom-kanban .s, .custom-kanban .s1, .custom-kanban .s2, .custom-kanban .se, .custom-kanban .sa, .custom-kanban .sb, .custom-kanban .sc, .custom-kanban .sd, .custom-kanban .sh, .custom-kanban .si, .custom-kanban .sx, .custom-kanban .sr, .custom-kanban .ss { color: #98C379; } /* 字符串：原谅绿 */
                .custom-kanban .k, .custom-kanban .kn, .custom-kanban .kc, .custom-kanban .kd, .custom-kanban .ow, .custom-kanban .kr, .custom-kanban .kp { color: #C678DD; font-weight: bold; } /* 关键字：风骚紫 */
                .custom-kanban .m, .custom-kanban .mi, .custom-kanban .mf, .custom-kanban .mh, .custom-kanban .il, .custom-kanban .mo, .custom-kanban .mb { color: #D19A66; } /* 数字：亮橙色 */
                .custom-kanban .nf, .custom-kanban .nc, .custom-kanban .fm { color: #61AFEF; } /* 函数/类名：天空蓝 */
                .custom-kanban .o { color: #56B6C2; } /* 运算符：青色 */
                .custom-kanban .nb, .custom-kanban .bp { color: #E5C07B; } /* 内置函数：淡黄色 */
                .custom-kanban .nd { color: #E5C07B; } /* 装饰器：淡黄色 */
                .custom-kanban .p { color: #ABB2BF; } /* 标点符号：浅灰白 */
                .custom-kanban .n, .custom-kanban .nx { color: #E0E0E0; } /* 默认变量：亮白色 */
            </style>
            """
            formatter = HtmlFormatter(noclasses=False, cssclass="custom-kanban", linenos='inline')
            raw_highlighted = highlight(code, PythonLexer(), formatter)
            highlighted_code = custom_css + raw_highlighted
        else:
            safe_code = code.replace('<', '&lt;').replace('>', '&gt;')
            highlighted_code = f'<pre style="background-color: #1E1E1E; color: #E0E0E0;">{safe_code}</pre>'

        html = f'<div style="margin-bottom: 20px;">'
        if not translation:
            html += f'<div style="color: #61AFEF; font-weight: bold; margin-bottom: 5px;">[{ts}] 代码快照</div>{highlighted_code}'
        else:
            html += f'<div style="color: #61AFEF; font-weight: bold; margin-bottom: 5px;">[{ts}] 捕获代码段</div>{highlighted_code}'
            html_translation = markdown.markdown(translation, extensions=['fenced_code', 'tables']) if HAS_RICH_RENDER else translation.replace('\n', '<br>')
            html += f"""
            <div style="color: #98C379; font-weight: bold; margin-bottom: 10px; margin-top: 15px;">🧠 架构师拆解</div>
            <div style="background-color: #252526; border-left: 4px solid #C678DD; color: #D4D4D4; padding: 15px; border-radius: 0 6px 6px 0;">
                {html_translation}
            </div>
            """
        html += '<hr style="border: 0; border-bottom: 1px dashed #3E4451; margin-top: 20px;"></div>'
        return html

    def handle_pure_code_drop(self, code, file_path):
        self.current_left_file_path = file_path
        # 现在左侧是真实的编辑器，直接将纯文本加载进去，引擎会瞬间自动高亮并生成行号！
        self.pure_code_view.setPlainText(code)

    def update_result(self, code, translation):
        html = self.generate_html_block(code, translation)
        self.ai_view.append(html)
        scrollbar = self.ai_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

# ==========================================
# 核心总线
# ==========================================
class LogicLens(QObject):
    msg_signal = pyqtSignal(str, int, int)
    result_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.cfg = load_config()
        self.cp = ControlPanel(self.cfg)
        
        from PyQt6.QtWidgets import QWidget as QW
        class Ball(QW):
            def __init__(self, controller):
                super().__init__()
                self.controller = controller
                self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                self.active = True
                self.is_hovered = False
                self.is_pressed = False
                self.resize(40, 40)
                self.move(100, 100)

            def paintEvent(self, e):
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 50))
                p.drawEllipse(4, 4, 32, 32)
                margin = 4 if not self.is_pressed else 6
                size = 40 - margin * 2
                gradient = QRadialGradient(margin + size * 0.3, margin + size * 0.3, size)
                
                if self.active:
                    light_col = QColor(130, 255, 170) if self.is_hovered else QColor(88, 214, 141)
                    dark_col = QColor(39, 174, 96) if self.is_hovered else QColor(46, 204, 113)
                else:
                    light_col = QColor(255, 150, 150) if self.is_hovered else QColor(241, 148, 138)
                    dark_col = QColor(192, 57, 43) if self.is_hovered else QColor(231, 76, 60)
                
                if self.is_pressed:
                    light_col = light_col.darker(120)
                    dark_col = dark_col.darker(120)

                gradient.setColorAt(0, light_col)
                gradient.setColorAt(1, dark_col)
                p.setBrush(gradient)
                p.drawEllipse(margin, margin, size, size)
                p.setPen(QColor(255, 255, 255, 100))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(margin+1, margin+1, size-2, size-2)

            def enterEvent(self, e):
                self.is_hovered = True; self.update()
            def leaveEvent(self, e):
                self.is_hovered = False; self.update()
            def mousePressEvent(self, e): 
                if e.button() == Qt.MouseButton.LeftButton:
                    self.is_pressed = True
                    self.pos_start = e.globalPosition().toPoint()
                    self.update()
            def mouseReleaseEvent(self, e):
                if e.button() == Qt.MouseButton.LeftButton:
                    self.is_pressed = False; self.update()
            def mouseDoubleClickEvent(self, e):
                self.active = not self.active; self.update()
            def mouseMoveEvent(self, e): 
                if e.buttons() == Qt.MouseButton.LeftButton:
                    self.move(self.pos() + (e.globalPosition().toPoint() - self.pos_start))
                    self.pos_start = e.globalPosition().toPoint()
            def contextMenuEvent(self, e):
                menu = QMenu(self)
                menu.setStyleSheet("""
                    QMenu { background-color: #2D2D30; color: #D4D4D4; border: 1px solid #555; border-radius: 4px; padding: 5px; }
                    QMenu::item { padding: 5px 20px; }
                    QMenu::item:selected { background-color: #007ACC; border-radius: 2px; }
                """)
                show_act = menu.addAction("⚙️ 显示主控面板")
                exit_act = menu.addAction("❌ 完全退出 LogicLens")
                act = menu.exec(e.globalPos())
                if act == show_act:
                    self.controller.cp.showNormal()
                    self.controller.cp.activateWindow()
                elif act == exit_act:
                    self.controller.app.quit()

        self.ball = Ball(self)
        self.cp.config_updated_signal.connect(self.update_cfg)
        self.cp.ai_file_dropped_signal.connect(self.process_ai_drop)
        self.msg_signal.connect(self.pop_bubble)
        self.result_signal.connect(self.cp.update_result)
        
        self.cp.show()
        self.ball.show()
        self.ctrl = False; self.bubble = None
        self.init_hooks()

    def update_cfg(self, c): self.cfg = c

    def pop_bubble(self, txt, x, y):
        if self.bubble: self.bubble.close()
        
        class BubbleBrowser(QTextBrowser):
            def mousePressEvent(self, e):
                if e.button() == Qt.MouseButton.LeftButton:
                    self.window().close()
                super().mousePressEvent(e)

        class Bubble(QWidget):
            def __init__(self, html_txt, px, py):
                super().__init__()
                self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating) 
                
                l = QVBoxLayout()
                self.setLayout(l)
                l.setContentsMargins(0, 0, 0, 0)
                
                self.tb = BubbleBrowser()
                self.tb.setHtml(html_txt)
                self.tb.setStyleSheet("""
                    QTextBrowser {
                        background: rgba(30, 30, 30, 245); 
                        color: #D4D4D4; 
                        padding: 15px; 
                        border: 1px solid #C678DD; 
                        border-radius: 8px; 
                        font-size: 10.5pt; 
                        line-height: 1.6;
                    }
                    QScrollBar:vertical { width: 8px; background: transparent; }
                    QScrollBar::handle:vertical { background: #666; border-radius: 4px; }
                    QScrollBar::handle:vertical:hover { background: #888; }
                """)
                
                self.tb.setMinimumWidth(350)
                self.tb.setMaximumWidth(550)
                self.tb.setMinimumHeight(100)
                self.tb.setMaximumHeight(700) 
                
                l.addWidget(self.tb)
                
                doc_height = self.tb.document().size().height() + 40
                self.resize(550, min(int(doc_height), 700))
                
                self.move(px + 15, py + 15)
                self.show()

        self.bubble = Bubble(txt, x, y)

    def init_hooks(self):
        def on_p(k): 
            if k in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]: self.ctrl = True
            
            if k == keyboard.Key.esc:
                if self.bubble:
                    self.bubble.close()
                    self.bubble = None
                    
        def on_r(k): 
            if k in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]: self.ctrl = False
        def on_c(x, y, b, p):
            if self.ball.active and b==mouse.Button.left and not p and self.ctrl:
                threading.Thread(target=self.work, args=(int(x), int(y))).start()
        keyboard.Listener(on_press=on_p, on_release=on_r).start()
        mouse.Listener(on_click=on_c).start()

    def process_ai_drop(self, content):
        self.cp.ai_view.append("<div style='color: #888; font-style: italic; margin-bottom: 10px;'>⏳ 已接收拖入文件，正在请求 AI 分析，请稍候...</div>")
        threading.Thread(target=self.work, args=(None, None, content)).start()

    def work(self, x=None, y=None, file_content=None):
        if file_content is not None:
            code = file_content
        else:
            pyperclip.copy("")
            c = keyboard.Controller()
            with c.pressed(keyboard.Key.ctrl): c.press('c'); c.release('c')
            time.sleep(0.15)
            code = pyperclip.paste()
            if not code.strip(): return
            
            loading_html = "<div style='color:#00FFCC;'>⚡ 抓取成功，透视中...</div>"
            self.msg_signal.emit(loading_html, x, y)
            
        if not code.strip(): return
        
        try:
            api_cfg = self.cfg["api_configs"][self.cfg["current_api_index"]]
            prompt = self.cfg["prompts"][self.cfg["current_prompt_index"]]["content"]
            
            api_url = api_cfg.get("api_url", "")
            api_model = api_cfg.get("api_model", "")
            api_key = api_cfg.get("api_key", "")
            
            if not api_url or not api_key:
                raise ValueError("请在面板中正确填写 API 地址与密钥！")

            resp = requests.post(api_url, 
                               headers={"Authorization": f"Bearer {api_key}"},
                               json={"model": api_model, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": code}]},
                               timeout=60).json()
            
            if 'error' in resp:
                raise Exception(resp['error'].get('message', str(resp['error'])))
                
            ans = resp['choices'][0]['message']['content']
            
            if file_content is None:
                display_text = ans.strip()
                safe_txt = display_text.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                
                final_html = f"""
                <div style='margin-bottom: 8px;'>{safe_txt}</div>
                <hr style='border: 0; border-bottom: 1px dashed #555; margin: 12px 0 8px 0;'>
                <div style='color: #888; font-size: 8.5pt; text-align: right;'>
                    ⌨️ 按 ESC 键 / 或鼠标点击此气泡立即关闭
                </div>
                """
                self.msg_signal.emit(final_html, x, y)
            
            self.result_signal.emit(code, ans)
            
        except Exception as e: 
            if file_content is None:
                err_html = f"<div style='color:#E74C3C;'>❌ 翻译失败，请查看面板大屏</div>"
                self.msg_signal.emit(err_html, x, y)
            self.result_signal.emit(code, f"调用出错: {str(e)}")

if __name__ == "__main__":
    LogicLens().app.exec()