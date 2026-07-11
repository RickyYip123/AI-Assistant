iimport os
import telebot
from collections import defaultdict
import google.generativeai as genai
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading


os.environ["GOOGLE_GENAI_API_VERSION"] = "v1"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)


model = genai.GenerativeModel(model_name='gemini-1.5-flash')

user_memories = defaultdict(list)
MAX_MEMORY_ROUNDS = 6  

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

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
        {"role": "user", "parts": [prompt_setup]},
        {"role": "model", "parts": ["Understood. I will act as a patient English tutor, correct your mistakes in Chinese with bold text, and keep our chat natural and fun! Let's chat! How was your day today?"]}
    ]
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def chat_with_gemini(message):
    chat_id = message.chat.id
    user_text = message.text

    if chat_id not in user_memories or not user_memories[chat_id]:
        user_memories[chat_id] = []

    history = user_memories[chat_id]
    
    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_text)
        ai_reply = response.text

        full_history = chat.get_history()

        while len(full_history) > (MAX_MEMORY_ROUNDS * 2):
            full_history.pop(0)  
            full_history.pop(0)  

        user_memories[chat_id] = full_history
        bot.reply_to(message, ai_reply)

    except Exception as e:
        bot.reply_to(message, f"Learning Assistant Notice: {str(e)}")

if __name__ == '__main__':
    print("Starting health check server...")
    threading.Thread(target=run_health_check, daemon=True).start()
    print("Gemini English Tutor Bot is running...")
    bot.infinity_polling()
