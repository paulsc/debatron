import os
import sys
import json
import logging
import coloredlogs
from telegram import Update
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler

from openai import AsyncOpenAI

PROMPT_PREAMBLE = """
You are a moderator in a group for political discussion, you return a score
for the last message sent in the group chat was. 0 is a bad message, 10 is a
good one. You return JSON, one score attribute and one message attribute, the
message is a short (50 words) message justifying the score. Your criterias are:
"""

class Bot:
    def __init__(self):
        self.MESSAGES = []
        self.LAST_SCORE = None
        self.gpt = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.telegram = ApplicationBuilder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()
        self.add_chat_handlers()

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

    async def aiquery(self, msg):
        formatted = {"role": "user", "content": msg}
        self.MESSAGES.append(formatted)
        self.MESSAGES = self.MESSAGES[-10:]
        current_user = self.MESSAGES[-1]["content"].split(":")[0]
        for msg in self.MESSAGES: print(msg["content"])
        gpt_messages = self.make_prompt() + self.MESSAGES
        print(gpt_messages)
        response = await self.gpt.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=gpt_messages,
            max_tokens=200)
        #print(f"Model used: {response.model}")
        answer = response.choices[0].message.content.strip()
        parsed = json.loads(answer)
        self.LAST_SCORE = parsed
        self.LAST_SCORE["user"] = current_user
        print(answer)
        return parsed

    def format_score(self, response):
        return f"Score: {response['score']}/10. {response['message']}"

    async def update_criterias_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def last_score_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = "none" if self.LAST_SCORE is None else self.format_score(self.LAST_SCORE)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        src = update.message.from_user.full_name
        msg = src + ":" + update.message.text
        logging.info("Got MSG> " + msg)
        response = await self.aiquery(msg)
        if response["score"] < 5:
            await update.message.reply_text(self.format_score(response))

    async def hello_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        criterias = self.read_criterias()
        intro_message = (
            "Hello! I'm a friendly moderator bot for political discussions. "
            "I evaluate messages based on the following criteria:\n\n"
            f"{criterias}\n\n"
            "I'm here to help maintain a positive and constructive conversation. "
            "Feel free to chat, and I'll provide feedback when necessary!"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=intro_message)

    def add_chat_handlers(self):
        self.telegram.add_handler(CommandHandler('last', self.last_score_handler))
        self.telegram.add_handler(CommandHandler('criterias', self.update_criterias_handler))
        self.telegram.add_handler(CommandHandler('hello', self.hello_handler))

        msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.message_handler)
        self.telegram.add_handler(msg_handler)

    def run(self):
        self.telegram.run_polling()

if __name__ == '__main__':
    coloredlogs.install(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
        level=logging.INFO
    )
    bot = Bot()
    bot.run()


