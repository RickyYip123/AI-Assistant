import os
import telebot
from collections import defaultdict
import google.generativeai as genai


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)


model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction=(
        "You are a friendly and patient English teacher. You are having a casual chat with the user. "
        "Guidelines:\n"
        "1. Use everyday conversational English. Keep your response within 3 sentences.\n"
        "2. Always end your response with a simple question to keep the conversation going.\n"
        "3. Correction Feedback Loop: If the user makes a grammatical mistake or uses unnatural English, "
        "first point it out in Chinese, provide the most natural expression in **bold text**, "
        "and then continue the conversation in English."
    )
)


user_memories = defaultdict(list)
MAX_MEMORY_ROUNDS = 6  

@bot.message_handler(commands=['start', 'reset'])
def send_welcome(message):
    chat_id = message.chat.id
    welcome_text = "Hi! I'm your English tutor. Let's chat! How was your day today?"
    
   
    user_memories[chat_id] = [{"role": "model", "parts": [welcome_text]}]
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def chat_with_gemini(message):
    chat_id = message.chat.id
    user_text = message.text

    
    if chat_id not in user_memories or not user_memories[chat_id]:
        user_memories[chat_id] = []

   
    if len(user_memories[chat_id]) > (MAX_MEMORY_ROUNDS * 2):
       
        user_memories[chat_id] = user_memories[chat_id][-(MAX_MEMORY_ROUNDS * 2):]
        
        if user_memories[chat_id][0]["role"] != "user":
            user_memories[chat_id] = user_memories[chat_id][1:]

    
    history = user_memories[chat_id]
    
    try:
        
        chat = model.start_chat(history=history)
        response = chat.send_message(user_text)
        ai_reply = response.text

        
        user_memories[chat_id] = chat.get_history()

      
        bot.reply_to(message, ai_reply)

    except Exception as e:
        bot.reply_to(message, f"Learning Assistant Notice: {str(e)}")

if __name__ == '__main__':
    print("Gemini English Tutor Bot is running...")
    bot.infinity_polling()
