import os
import sys
import json
import logging
import coloredlogs
from telegram import Update
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler

import openai
from openai import AsyncOpenAI

OPENAIKEY = os.environ.get("OPENAI_API_KEY")
BOTTOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

PROMPT_PREAMBLE = "You are a moderator in a group for political discussion, you return a score for the last message sent in the group chat was. 0 is a bad message, 10 is a good one. You return JSON, one score attribute and one message attribute, the message is a short (50 words) message justifying the score. Your criterias are:"

MESSAGES = []
LAST_SCORE = None

aiclient = AsyncOpenAI(api_key=OPENAIKEY)

def make_prompt():
    criterias = None
    criterias = read_criterias()
    prompt = PROMPT_PREAMBLE + "\n" + criterias.replace('\n', '')
    return [{"role": "system", "content": prompt}]

def read_criterias():
    with open('criterias.txt') as file:
        return file.read()

def update_criterias(criterias):
    with open('criterias.txt', 'w') as file:
            file.write(criterias)

async def aiquery(msg):
    global MESSAGES, LAST_SCORE
    formatted = {"role": "user", "content": msg}
    MESSAGES.append(formatted)
    MESSAGES = MESSAGES[-10:]
    current_user = MESSAGES[-1]["content"].split(":")[0]
    for msg in MESSAGES: print(msg["content"])
    gpt_messages = make_prompt() + MESSAGES
    print(gpt_messages)
    response = await aiclient.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=gpt_messages,
        max_tokens=200)
    #print(f"Model used: {response.model}")
    answer = response.choices[0].message.content.strip()
    parsed = json.loads(answer)
    LAST_SCORE = parsed
    LAST_SCORE["user"] = current_user
    print(answer)
    return parsed


coloredlogs.install(
    fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
    level=logging.INFO
)

def format_score(response):
    msg = ""
    if "user" in response:
        msg = f"Last message by {response['user']}:\n"
    msg = msg + f"Score: {response['score']}/10. {response['message']}"
    return msg

async def update_criterias_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    split = update.message.text.split(None, 1)
    if len(split) == 1:
        await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text="No new criterias provided.")
        return
    newcrits = split[1]
    logging.info(f"Updating criterias: {newcrits}")
    update_criterias(newcrits)
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text="Criterias updated.")

async def last_score_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "none" if LAST_SCORE is None else format_score(LAST_SCORE)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    src = update.message.from_user.full_name
    msg = src + ":" + update.message.text
    logging.info("Got MSG> " + msg)
    response = await aiquery(msg)
    if response["score"] < 5:
        await update.message.reply_text(format_score(response))

async def hello_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    criterias = read_criterias()
    intro_message = (
        "Hello! I'm a friendly moderator bot for political discussions. "
        "I evaluate messages based on the following criteria:\n\n"
        f"{criterias}\n\n"
        "I'm here to help maintain a positive and constructive conversation. "
        "Feel free to chat, and I'll provide feedback when necessary!"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=intro_message)

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOTTOKEN).build()

    application.add_handler(CommandHandler('last', last_score_handler))
    application.add_handler(CommandHandler('criterias', update_criterias_handler))
    application.add_handler(CommandHandler('hello', hello_handler))

    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler)
    application.add_handler(msg_handler)

    application.run_polling()


