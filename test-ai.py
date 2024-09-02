import re
import sys
import json
import shutil
import asyncio
import logging
import os
from typing import List
from dotenv import load_dotenv
load_dotenv(override=True)
from openai import AsyncOpenAI

TESTRUNS_FOLDER = "testruns"
CHATLOG_FILE = os.path.join(TESTRUNS_FOLDER, "immigration.log")
CHAT_HISTORY_CONTEXT = 10

SYSTEM_PROMPT = """
You are a helpful assistant that scores chat messages. 0 is a bad message, 10 is
a good one. You return JSON, one score attribute and one message attribute, the
message is a short (20 words) message justifying the score. 
Your criterias for scoring are:
- Don't be adversarial, but instead constructive and try to build consensus.
- Don't be condescending or sarcastic, but respectful in tone.
"""

USER_PROMPT_HISTORY = "Here is the partial history of the conversation for context:"
USER_PROMPT_LAST_MESSAGE = "Please provide a score for the last message, which is:"

if len(sys.argv) != 2:
    print("Usage: python test-ai.py <folder_name>")
    sys.exit(1)

folder_name = os.path.join(TESTRUNS_FOLDER, sys.argv[1])
if os.path.exists(folder_name):
    shutil.rmtree(folder_name)
os.makedirs(folder_name)

with open(os.path.join(folder_name, 'config.txt'), 'w') as file:
    file.write(f"CHAT_HISTORY_CONTEXT={CHAT_HISTORY_CONTEXT}\n")
    file.write(f"SYSTEM_PROMPT=\n{SYSTEM_PROMPT}\n")

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(os.path.join(folder_name, "test-ai.log")),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger('test-ai')

gpt = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def parse_chat_log(file_path):
    messages = []
    with open(file_path, 'r') as file:
        lines = file.readlines()

    current_message = ""
    for line in lines:
        if starts_with_timestamp(line):
            if len(current_message) > 0: # finalize the last processed message
                messages.append(current_message.strip())
            current_message = line.split("]", 1)[1] # split after the group name
        else: # we are looking at a multi-line message
            current_message += line

    if len(current_message) > 0:
        messages.append(current_message.strip())

    return messages

def starts_with_timestamp(line):
    # check if line starts with something like 2024-08-31 11:29:21,379
    return re.match(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2},\d{3}', line) is not None

def gpt_message(role, content):
    return { "role": role, "content": content }

async def chatgpt_query(texts: List[str]):
    prompt = gpt_message("system", SYSTEM_PROMPT)

    user_messages = []

    if len(texts) == 0:
        raise ValueError("No texts provided for chatgpt_query")
    if len(texts) == 1:
        user_messages.append(USER_PROMPT_LAST_MESSAGE)
        user_messages.append(texts[0])
    else:
        user_messages.append(USER_PROMPT_HISTORY)
        for text in texts[:-1]:
            user_messages.append(text)
        user_messages.append(USER_PROMPT_LAST_MESSAGE)
        user_messages.append(texts[-1])

    gpt_messages = [ prompt ] + [ gpt_message("user", text) for text in user_messages ]
    #for message in gpt_messages: print(message)

    response = await gpt.chat.completions.create(
        model="gpt-4", 
        messages=gpt_messages,
        max_tokens=200)
    answer = response.choices[0].message.content.strip()
    parsed = json.loads(answer)
    return parsed

async def main():
    logger.info("Starting test-ai.py")
    chat_messages = []

    messages = parse_chat_log(CHATLOG_FILE)
    counter = 0
    for message in messages:
        logger.info("")
        if "\n" in message:
            logger.info(message.split('\n')[0] + " [TRUNCATED]")
        else:
            logger.info(message)
        chat_messages.append(message)

        parsed = await chatgpt_query(chat_messages[-CHAT_HISTORY_CONTEXT:])
        logger.info(f"\033[92m{parsed['score']}/10 - {parsed['message']}\033[0m")

        counter += 1
        if counter % 1 == 0:
            input("Press Enter to continue...")

if __name__ == "__main__":
    asyncio.run(main())
