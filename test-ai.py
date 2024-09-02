import re
import sys
import asyncio
import logging
from main import Bot
from cache import create_mock_message

logger = logging.getLogger('test-ai')
logger.setLevel(logging.INFO)
logger.propagate = False  # Add this line to disable propagation

file_handler = logging.FileHandler("test-ai.log")
console_handler = logging.StreamHandler()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Disable all other loggers
logging.getLogger().handlers = []
logging.getLogger().addHandler(logging.NullHandler())

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

async def main():
    bot = Bot()
    logger.info("Starting test-ai.py")

    messages = parse_chat_log('immigration.log')
    counter = 0
    for message in messages:
        logger.info("---")
        logger.info(message)

        parsed = await bot.chatgpt_query(message)
        logger.info(parsed)

        counter += 1
        if counter % 10 == 0:
            input("Press Enter to continue...")

if __name__ == "__main__":
    asyncio.run(main())
