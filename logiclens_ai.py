import os
import requests

# ==========================================
# 配置区：填入你的 API 密钥
# ==========================================
# 默认优先读取环境变量，如果没有则使用后面的字符串。
# 如果你测试时没有 key，可以直接在下面填入字符串，例如 "sk-xxxxxxxx"
API_KEY = os.getenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
API_URL = "https://api.deepseek.com/chat/completions" # DeepSeek 官方接口

# 核心灵魂：架构师级 Prompt
# 强制大模型闭嘴，禁止它像个初级程序员一样给你解释什么是 for 循环
SYSTEM_PROMPT = """你是一个极致冷酷的逻辑透视机。
输入是 Python 代码，禁止解释任何语法，只能输出高维度的业务意图和资源操作。
请用最简练的大白话，按逻辑步骤输出。

输出格式必须类似如下范例：
- [IO操作]：去硬盘指定路径读取文件内容。
- [算力消耗]：将文件内容计算出 MD5 唯一特征码。
- [逻辑分流]：拿着特征码去数据库里比对，如果在库里就拦截（返回 False），否则放行（返回 True）。"""

def analyze_logic(code_context: str) -> str:
    """
    核心动作：调用大模型 API，将代码转化为降维的架构师语言。
    """
    if not code_context or not code_context.strip():
        return "⚠️ 未接收到有效代码上下文。"

    print("[AI Engine] 正在连接大模型大脑...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 负载配置
    payload = {
        "model": "deepseek-chat",  # 指定模型
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请透视以下代码的物理意图：\n\n{code_context}"}
        ],
        # ⚠️ 架构师细节：把 temperature 调到极低 (0.1)
        # 这会让 AI 的回答非常确定、机械、没有废话，像机器一样精准，不会每次给你不同的修辞手法。
        "temperature": 0.1 
    }

    try:
        # 发起请求，设置 15 秒超时防止卡死
        response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status() # 检查 HTTP 错误
        
        # 解析返回结果
        result = response.json()
        translation = result['choices'][0]['message']['content']
        return translation
        
    except requests.exceptions.RequestException as e:
        # 网络或接口报错的防呆处理
        return f"❌ [API 调用失败] 请检查网络或 API_KEY 是否有效。\n具体报错: {str(e)}"
    except KeyError:
        return "❌ [解析失败] 大模型返回的数据格式异常。"

# ==========================================
# 本地测试与推演演示
# ==========================================
if __name__ == "__main__":
    # 模拟组件 2 (AST聚合器) 抛过来的完美上下文
    mock_context_from_ast = """
    def check_video_uniqueness(file_path, database):
        content = open(file_path, 'rb').read()
        video_hash = hashlib.md5(content).hexdigest()
        if video_hash in database:
            return False
        return True
    """
    
    print("🔻 接收到 AST 传来的完整逻辑块：")
    print(mock_context_from_ast)
    print("-" * 40)
    
    if API_KEY == "your_deepseek_api_key_here":
        print("⚠️ 提示：你还没填入真实的 API_KEY，稍后会看到报错提示，这是正常的，用于验证容错机制。")
        
    translation_result = analyze_logic(mock_context_from_ast)
    
    print("\n🎯 AI 降维解析结果：")
    print("=" * 40)
    print(translation_result)
    print("=" * 40)