import os
import telebot
from collections import defaultdict
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
AGNES_API_KEY = os.getenv("AGNES_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

user_memories = defaultdict(list)
MAX_MEMORY_ROUNDS = 6  

# 1. 网页健康检查服务器配置
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Chat Bot is alive!")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 2. 机器人指令逻辑
@bot.message_handler(commands=['start', 'reset'])
def send_welcome(message):
    chat_id = message.chat.id
    welcome_text = "Hi! I'm your English tutor. Let's chat! How was your day today?"
    
    prompt_setup = (
        "从现在开始，你是一位风趣幽默、非常有耐心的真人外教。你的目标是帮助用户通过日常闲聊提升英文对话能力。\n"
        "# Guidelines\n"
        "1. 语言难度：请使用日常口语（Colloquial English），避免使用过于复杂的学术词汇或考研词汇。\n"
        "2. 互动方式：每次回答控制在 2-3 句话以内，不要说成长篇大论。每次回答的结尾必须抛出一个简单、自然的问题，引导用户继续说下去。\n"
        "3. 双语机制：当用户用中文提问或表达遇到困难时，可以用中文解答，但鼓励用户用英文回应。\n"
        "# Correction Feedback Loop（核心纠错机制）\n"
        "如果用户的英文表达有明显的语法错误，或者表达很不地道，请按照以下格式回应：\n"
        "1. 先给出赞美或理解（如：I understand what you mean! / Great try!）\n"
        "2. 【地道表达】：用加粗字体给出 1 个最自然、地道的日常说法。\n"
        "3. 【继续对话】：顺着这个话题继续聊下去，并提出下一个问题。\n"
        "（注意：不要长篇大论讲解语法，只给地道句子，保持对话流畅。）"
    )
    
    user_memories[chat_id] = [
        {"role": "system", "content": prompt_setup},
        {"role": "assistant", "content": "Understood. I will act as a patient English tutor, correct your mistakes in Chinese with bold text, and keep our chat natural and fun! Let's chat! How was your day today?"}
    ]
    bot.reply_to(message, welcome_text)

# 3. 机器人聊天核心逻辑
@bot.message_handler(func=lambda message: True)
def chat_with_agnes(message):
    chat_id = message.chat.id
    user_text = message.text

    if chat_id not in user_memories or not user_memories[chat_id]:
        send_welcome(message)
        return

    user_memories[chat_id].append({"role": "user", "content": user_text})
    
    url = "https://apihub.agnes-ai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "agnes-2.0-flash",
        "messages": user_memories[chat_id]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_data = response.json()

        if "choices" in res_data and res_data["choices"]:
            ai_reply = res_data["choices"][0]["message"]["content"]
            print(f"====== 新消息 ======")
            print(f"用户 [{chat_id}] 说: {user_text}")
            print(f"AI 回复: {ai_reply}")
            print(f"====================")
            
            user_memories[chat_id].append({"role": "assistant", "content": ai_reply})

            while len(user_memories[chat_id]) > (MAX_MEMORY_ROUNDS * 2 + 1):
                user_memories[chat_id].pop(1) 
                user_memories[chat_id].pop(1)

            bot.reply_to(message, ai_reply)
        else:
            error_msg = res_data.get("error", {}).get("message", "Unknown API Error")
            bot.reply_to(message, f"Agnes AI Notice: {error_msg}")
            user_memories[chat_id].pop()

    except Exception as e:
        bot.reply_to(message, f"Connection Notice: {str(e)}")
        if user_memories[chat_id]:
            user_memories[chat_id].pop()

# 4. 完美的唯一入口启动器（必须在最底下）
if __name__ == '__main__':
    print("Starting health check server...")
    threading.Thread(target=run_health_check, daemon=True).start()
    print("Agnes AI English Tutor Bot is running...")
    bot.infinity_polling()
