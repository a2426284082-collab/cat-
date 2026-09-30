import ast

def extract_context_block(full_code: str, snippet: str) -> str:
    """
    核心魔法：基于 AST（抽象语法树）的上下文自动扩容。
    输入：全文代码 (full_code)，以及用户鼠标划选的可能残缺的片段 (snippet)。
    输出：该片段所属的完整函数体或类代码。
    """
    if not snippet or not snippet.strip():
        return ""

    # 步骤 1: 物理定位 —— 找到 snippet 在全文中的具体行号
    start_idx = full_code.find(snippet)
    if start_idx == -1:
        # 如果在全文里找不到这个片段（极少发生，除非剪贴板异常），降级返回原片段
        return snippet
    
    # 计算起始行号和结束行号 (AST 的 lineno 是从 1 开始的)
    start_line = full_code.count('\n', 0, start_idx) + 1
    end_line = start_line + snippet.count('\n')

    # 步骤 2: 逻辑解析 —— 将全文转化为结构树
    try:
        tree = ast.parse(full_code)
    except SyntaxError:
        # 如果用户的全文本身就有致命的语法错误导致无法解析，
        # 则放弃智能扩容，降级返回原片段。
        print("[AST Engine] 警告: 全文存在语法错误，降级为文本匹配。")
        return snippet

    # 步骤 3: 寻找逻辑包围盒 (Enclosing Node)
    best_node = None
    # 架构师视角：我们只关心这三种具有“闭环逻辑”的关节节点
    target_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    for node in ast.walk(tree):
        if isinstance(node, target_types):
            # 确保节点有行号属性 (极少数动态生成的节点可能没有)
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                # 判定门：残缺的 snippet 是否完全落在这个节点的物理行号范围内？
                if node.lineno <= start_line and end_line <= node.end_lineno:
                    
                    # 寻找“最小且最精确”的包围盒
                    # （例如：如果 snippet 在一个类里面的函数里，我们优先提取函数，而不是整个庞大的类）
                    if best_node is None:
                        best_node = node
                    else:
                        current_size = node.end_lineno - node.lineno
                        best_size = best_node.end_lineno - best_node.lineno
                        if current_size < best_size:
                            best_node = node

    # 步骤 4: 结果输出
    if best_node:
        # 使用 ast 的内置方法，完美切割出该节点对应的源代码
        return ast.get_source_segment(full_code, best_node)
    else:
        # 如果代码没有写在任何函数或类里（比如直接写在最外层的全局脚本），
        # 我们认为它没有上层上下文，直接返回用户选中的原片段。
        return snippet

# ==========================================
# 本地测试与推演演示
# ==========================================
if __name__ == "__main__":
    # 模拟一份当前你正在阅读的复杂文件全文
    mock_full_code = """
import hashlib

def process_data(user_id):
    pass

def check_video_uniqueness(file_path, database):
    content = open(file_path, 'rb').read()
    video_hash = hashlib.md5(content).hexdigest()
    if video_hash in database:
        return False
    return True

class Uploader:
    def upload(self):
        print("Uploading...")
"""

    # 模拟场景：你鼠标手滑，只选中了非常残缺的、不包含上下文的 2 行代码
    # 对应我们之前比喻的 "H2 + O"
    mock_selected_snippet = """ideo_hash = hashlib.md5(content).hexdigest()
    if video_hash in datab"""

    print("🔻 用户实际划选的（残缺）代码：")
    print("-" * 30)
    print(mock_selected_snippet)
    print("-" * 30)

    # 核心引擎启动
    print("\n🟢 AST引擎开始推演上下文...\n")
    context_code = extract_context_block(mock_full_code, mock_selected_snippet)

    print("🎯 AST 自动补全后的完整逻辑块：")
    print("=" * 40)
    print(context_code)
    print("=" * 40)
    print("\n💡 架构师注：可以看到，无论你选得多残缺，程序都完美抓取了整个 check_video_uniqueness 函数！")