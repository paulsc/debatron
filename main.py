import os
import sys
import json
import logging
import coloredlogs

from telegram import Update, Message
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv(override=True)

from cache import Cache

GPT_MODEL = "gpt-4"
#GPT_MODEL = "gpt-3.5-turbo"
CACHE_SIZE = 1000
PROMPT_PREAMBLE = """
You are a moderator in a group for political discussion, you return a score
for the last message sent in the group chat was. 0 is a bad message, 10 is a
good one. You return JSON, one score attribute and one message attribute, the
message is a short (50 words) message justifying the score. Your criterias are:
"""

class Bot:
    def __init__(self):
        self.chat_messages = []
        self.score_cache = Cache(CACHE_SIZE)

        self.setup_loggers()
        self.gpt = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.telegram = ApplicationBuilder().token(TG_TOKEN).build()
        self.add_chat_handlers()

    @staticmethod
    def format_message(message):
        return f"{message.from_user.full_name}: {message.text}"

    @staticmethod
    def format_score(response):
        return f"Score: {response['score']}/10. {response['message']}"

    def make_prompt(self):
        criterias = None
        criterias = self.read_criterias()
        prompt = PROMPT_PREAMBLE + "\n" + criterias.replace('\n', '')
        return [{"role": "system", "content": prompt}]

    def read_criterias(self):
        with open('criterias.txt') as file:
            return file.read()

    def update_criterias(self, criterias):
        with open('criterias.txt', 'w') as file:
            file.write(criterias)

    async def analyze(self, message: Update):
        if message in self.score_cache:
            return self.score_cache[message]

        self.chat_messages.append(message)
        self.chat_messages = self.chat_messages[-10:]

        text = Bot.format_message(message)
        parsed = await self.chatgpt_query(text)

        self.score_cache[message] = parsed
        return parsed

    async def chatgpt_query(self, text: str):
        gpt_message = { "role": "user", "content": text }
        gpt_messages = self.make_prompt() + [gpt_message]

        response = await self.gpt.chat.completions.create(
            model=GPT_MODEL, 
            messages=gpt_messages,
            max_tokens=200)
        answer = response.choices[0].message.content.strip()
        parsed = json.loads(answer)
        logging.info(answer)
        return parsed

    async def update_criterias_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info(f"/criterias handler called")
        split = update.message.text.split(None, 1)
        if len(split) == 1:
            await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text="No new criterias provided.")
            return
        newcrits = split[1]
        logging.info(f"Updating criterias: {newcrits}")
        self.update_criterias(newcrits)
        await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text="Criterias updated.")

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.edited_message:
            logging.info(f"Skipping message edit by {update.edited_message.from_user.full_name}")
            return
        chat_title = update.effective_chat.title or "Private Chat"
        message = f"[{chat_title}] {update.message.from_user.full_name}: {update.message.text}"
        self.chat_logger.info(message)
        response = await self.analyze(update.message)
        #if response["score"] < 5:
        #    await update.message.reply_text(Bot.format_score(response))

    async def hello_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info(f"/hello handler called")
        criterias = self.read_criterias()
        intro_message = (
            "Hello! I'm a friendly moderator bot for political discussions. "
            "I evaluate messages based on the following criteria:\n\n"
            f"{criterias}\n\n"
            "I'm here to help maintain a positive and constructive conversation. "
            "Feel free to chat, and I'll provide feedback when necessary!"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=intro_message)

    async def review_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info(f"/review handler called")
        if not update.message.reply_to_message:
            await context.bot.send_message(chat_id=update.effective_chat.id, 
                text="Please reply to the message you want to review with /review.")
            return
        message = update.message.reply_to_message
        response = await self.analyze(message)
        msg = Bot.format_score(response)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg,
            reply_to_message_id=message.message_id
        )

    def add_chat_handlers(self):
        self.telegram.add_handler(CommandHandler('hello', self.hello_handler))
        self.telegram.add_handler(CommandHandler('criterias', self.update_criterias_handler))
        self.telegram.add_handler(CommandHandler('review', self.review_handler))

        msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.message_handler)
        self.telegram.add_handler(msg_handler)

    def setup_loggers(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s %(message)s',
            handlers=[
                logging.FileHandler('debatron.log'),
                logging.StreamHandler()
            ]
        )

        coloredlogs.install(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
            level=logging.INFO
        )

        logging.getLogger("httpx").setLevel(logging.WARNING)

        self.chat_logger = logging.getLogger('chat')
        self.chat_logger.setLevel(logging.INFO)
        chat_handler = logging.FileHandler('chat.log')
        chat_formatter = logging.Formatter('%(asctime)s - %(message)s')
        chat_handler.setFormatter(chat_formatter)
        self.chat_logger.addHandler(chat_handler)

    def run(self):
        logging.info("Bot started")
        self.telegram.run_polling()

if __name__ == '__main__':
    bot = Bot()
    bot.run()


