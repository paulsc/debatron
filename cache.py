from collections import OrderedDict, deque
from telegram import User, Chat, Message

# Class to cache AI responses, key is a telegram message
# value is the response from chatgpt

class Cache:
    def __init__(self, max_size=100):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.key_queue = deque()

    def move_to_end(self, key):
        if key in self.key_queue:
            self.key_queue.remove(key)
            self.key_queue.append(key)

    def make_key(self, message: Message):
        return (message.chat_id, message.message_id)

    def __setitem__(self, key: Message, value):
        key = self.make_key(key)
        if key in self.cache:
            # Move the key to the end to mark it as most recently used
            self.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                oldest = self.key_queue.popleft()
                del self.cache[oldest]
            self.key_queue.append(key)
        self.cache[key] = value

    def __getitem__(self, key: Message):
        key = self.make_key(key)
        self.move_to_end(key)
        return self.cache[key]

    def get(self, key: Message):
        key = self.make_key(key)
        return self.cache.get(key)

    def __contains__(self, key: Message):
        key = self.make_key(key)
        return key in self.cache

    def __str__(self):
        return "CACHE " + "-"*24 + "\n" + "\n".join(
            f"{key}: {value}" for key, value in self.cache.items()) + "\n" + "-"*30

def create_mock_message(chat_id, message_id, user_id, text):
    user = User(id=user_id, first_name="Test", is_bot=False)
    chat = Chat(id=chat_id, type="private")
    return Message(message_id=message_id, from_user=user, chat=chat, 
                      date=None, text=text)

if __name__ == "__main__":
    cache = Cache(max_size=3)

    update1 = create_mock_message(chat_id=1, message_id=1, user_id=1, text="msg1")
    update2 = create_mock_message(chat_id=1, message_id=2, user_id=1, text="msg2")
    update3 = create_mock_message(chat_id=2, message_id=2, user_id=1, text="msg3")
    update4 = create_mock_message(chat_id=2, message_id=1, user_id=1, text="msg4")

    cache[update1] = {"score": 1, "message": "test"}
    assert update1 in cache

    cache[update2] = {"score": 1, "message": "test"}
    cache[update3] = {"score": 1, "message": "test"}
    cache[update4] = {"score": 1, "message": "test"}
    assert update1 not in cache

    print(cache)
