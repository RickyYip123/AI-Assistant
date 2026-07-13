import os
import telebot
from collections import defaultdict
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import json
import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

DB_FILE = "assistant_db.json"

def load_memories():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return defaultdict(list, json.load(f))
        except Exception:
            return defaultdict(list)
    return defaultdict(list)

def save_memories():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(user_memories, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存记忆失败: {e}")

user_memories = load_memories()
MAX_MEMORY_ROUNDS = 6  # 进一步缩短记忆轮数，搭配联网搜索能让整体积缩减，极大节省免费层额度

# 🎯 全新调整的精简生活助理人设
PROMPT_SETUP = (
    "从现在开始，你是哥的专属生活AI助理。你的核心任务是帮哥管理日常琐事、记录各种备忘，并随时解答哥在生活中遇到的任何问题。\n"
    "说话要轻松、接地气、自然、精炼，像个有默契的身边助手。\n\n"
    "# 1. 日常事务记录规范\n"
    "当哥或用户提到‘帮我记录’、‘提醒我’或需要备忘时，用最简短安心的口吻确认（如：‘好勒哥，帮你记下来了！’），并清晰列出要点。\n\n"
    "# 2. 联网搜索与极简回复规范\n"
    "当你使用内置的谷歌实时搜索查询生活信息（如查餐厅、查新闻、查路线）时：\n"
    "- **核心原则：短小精悍，拒绝长篇大论。** 每次回复必须控制在3句以内，直接给最精准的答案或推荐名单。\n"
    "- 严禁大段搬运网页内容，只保留哥最关心的核心信息，字数一定要精简！"
)

# 1. 网页健康检查服务器
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"AI Assistant with Search is alive!")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 2. 指令逻辑
@bot.message_handler(commands=['start', 'reset'])
def send_welcome(message):
    chat_id = str(message.chat.id)
    welcome_text = "遵命！生活助理已就位。哥，有什么需要我帮你记下，或者有什么想打听的随时发给我！"
    
    user_memories[chat_id] = [
        {"role": "model", "content": "已就位，随时听候调遣。"}
    ]
    save_memories()
    bot.reply_to(message, welcome_text)

# 3. 聊天核心逻辑（联网搜索 + 严格字数卡死 + 自动抗限流）
@bot.message_handler(func=lambda message: True)
def chat_with_assistant(message):
    chat_id = str(message.chat.id)
    user_text = message.text

    if chat_id not in user_memories or not user_memories[chat_id]:
        user_memories[chat_id] = [{"role": "model", "content": "已就位。"}]

    user_memories[chat_id].append({"role": "user", "content": user_text})
    
    model_name = "gemini-3.5-flash"
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
        # 🌐 开启谷歌官方【实时网络搜索】功能
        "tools": [{"googleSearch": {}}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 300  # 💾 🔴 核心重磅升级：硬性拦截单次最大返回字数，杜绝大长文爆配额！
        }
    }

    max_retries = 3
    retry_delay = 10 
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            res_data = response.json()

            if response.status_code == 200 and "candidates" in res_data:
                ai_reply = res_data['candidates'][0]['content']['parts'][0]['text']
                
                print(f"====== AI 助理 (联网+限字模式) ======")
                print(f"用户 [{chat_id}] 发送: {user_text}")
                print(f"助理响应:\n{ai_reply}")
                print(f"==============================")
                
                user_memories[chat_id].append({"role": "model", "content": ai_reply})

                while len(user_memories[chat_id]) > (MAX_MEMORY_ROUNDS * 2 + 1):
                    user_memories[chat_id].pop(1) 
                    user_memories[chat_id].pop(1)

                save_memories()
                bot.reply_to(message, ai_reply)
                return 

            elif response.status_code == 429 or "RESOURCE_EXHAUSTED" in str(res_data):
                print(f"⚠️ 触发限流，正在进行第 {attempt + 1} 次重试...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    bot.reply_to(message, "哥，排队的人有点多，谷歌免费层正在缓冲，麻烦过半分钟再发给我试试！")
                    if user_memories[chat_id]: user_memories[chat_id].pop()
                    return
            else:
                error_msg = res_data.get("error", {}).get("message", "Unknown Google API Error")
                bot.reply_to(message, f"助理服务提示: {error_msg}")
                if user_memories[chat_id]: user_memories[chat_id].pop()
                return

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            bot.reply_to(message, f"连接异常: {str(e)}")
            if user_memories[chat_id]: user_memories[chat_id].pop()
            return

if __name__ == '__main__':
    print("Starting health check server...")
    threading.Thread(target=run_health_check, daemon=True).start()
    print("AI Assistant Bot with Short-Search is running...")
    bot.infinity_polling()
