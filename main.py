import os
import telebot
from collections import defaultdict
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

user_memories = defaultdict(list)
MAX_MEMORY_ROUNDS = 10  # 助理需要更长的上下文记忆

# 🎯 全新升级：AI 高效助理硬核提示词（明细、教导、工作流）
PROMPT_SETUP = (
    "从现在开始，你是一位顶级的高效AI助理。你的名字叫鱼。你的唯一目标是帮助老板理清思路、管理任务、构建工作流，并精准记录一切事务。\n"
    "请完全丢弃任何英文老师、口语对练的设定。使用中文进行严谨、高效、一针见血的沟通。\n\n"
    "# 核心回复规范（严格执行三步结构）\n"
    "你的任何分析、回答或建议，必须清晰包含以下三个模块：\n"
    "1. **【明细】**：精准拆解老板提出的问题或任务核心，列出核心关键点，拒绝废话。\n"
    "2. **【教导】**：提供专业的逻辑指导、核心原理或认知层面的策略建议。\n"
    "3. **【工作流】**：给出清晰的第1步、第2步、第3步具体执行动作（Workflow），让老板能够立刻无脑执行。\n\n"
    "# 任务记录规范\n"
    "当老板提到‘帮我记录’、‘提醒我’或列出待办事项时，你必须在【明细】中明确归纳出该任务的时间、地点和事件，并以极其肯定的语气确认：‘遵命老板，已为您记录该事项。’"
)

# 1. 网页健康检查服务器配置
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Assistant Bot is alive!")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 2. 机器人指令逻辑
@bot.message_handler(commands=['start', 'reset'])
def send_welcome(message):
    chat_id = message.chat.id
    welcome_text = "遵命，老板！AI助理已就位。请发送您需要梳理的任务、工作流，或需要我为您记录的事情。"
    
    user_memories[chat_id] = [
        {"role": "model", "content": "已就位，随时听候调遣。将严格按照【明细】、【教导】、【工作流】结构为您高效处理事务。"}
    ]
    bot.reply_to(message, welcome_text)

# 3. 机器人聊天核心逻辑
@bot.message_handler(func=lambda message: True)
def chat_with_assistant(message):
    chat_id = message.chat.id
    user_text = message.text

    if chat_id not in user_memories or not user_memories[chat_id]:
        send_welcome(message)
        return

    user_memories[chat_id].append({"role": "user", "content": user_text})
    
    model_name = "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    formatted_contents = []
    for msg in user_memories[chat_id]:
        formatted_contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })
        
    payload = {
        "contents": formatted_contents,
        "systemInstruction": {
            "parts": [{"text": PROMPT_SETUP}]
        },
        "generationConfig": {
            "temperature": 0.3  # 降低随机性，让助理的回答更严谨稳定
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        res_data = response.json()

        if response.status_code == 200 and "candidates" in res_data:
            ai_reply = res_data['candidates'][0]['content']['parts'][0]['text']
            
            print(f"====== AI 助理模式 ======")
            print(f"用户 [{chat_id}] 安排任务: {user_text}")
            print(f"助理响应:\n{ai_reply}")
            print(f"==============================")
            
            user_memories[chat_id].append({"role": "model", "content": ai_reply})

            while len(user_memories[chat_id]) > (MAX_MEMORY_ROUNDS * 2 + 1):
                user_memories[chat_id].pop(1) 
                user_memories[chat_id].pop(1)

            bot.reply_to(message, ai_reply)
        else:
            error_msg = res_data.get("error", {}).get("message", "Unknown Google API Error")
            bot.reply_to(message, f"助理服务提示: {error_msg}")
            user_memories[chat_id].pop()

    except Exception as e:
        bot.reply_to(message, f"连接异常: {str(e)}")
        if user_memories[chat_id]:
            user_memories[chat_id].pop()

# 4. 入口启动器
if __name__ == '__main__':
    print("Starting health check server...")
    threading.Thread(target=run_health_check, daemon=True).start()
    print("AI Assistant Bot is running...")
    bot.infinity_polling()
