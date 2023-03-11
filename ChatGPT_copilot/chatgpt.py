"""
@File        :  chatgpt
@Contact     :  dlf43@qq.com
@Author      :  Randool
@Create Time :  2023/3/9
@Version     :  1.0
@Description :  None
"""
import glob
import json
import os.path
from typing import List, Optional

import openai
import tiktoken
from nonebot.log import logger


def num_tokens_from_messages(messages: List[dict], model="gpt-3.5-turbo-0301") -> int:
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo-0301":  # note: future models may deviate from this
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
  See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")


class ChatGPT:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    @staticmethod
    def interact_chatgpt(
            message_history: List[dict], model: str = "gpt-3.5-turbo", temperature: float = 0,
    ) -> dict:
        """ See: https://platform.openai.com/docs/guides/chat/introduction """
        # [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {"role": "user", "content": "Who won the world series in 2020?"},
        #     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        #     {"role": "user", "content": "Where was it played?"}
        # ]
        response = openai.ChatCompletion.create(
            model=model,
            messages=message_history,
            temperature=temperature,
        )
        response_message = dict(response["choices"][0]["message"])
        return response_message


class DialogManager(dict):
    """ user_id ==> [{"role": "", "content": ""}, ...] """

    def __init__(self, save_dir: str, dialog_max_length: int = 3000):
        super().__init__()
        self.save_dir = save_dir
        self.dialog_max_length = dialog_max_length

        os.makedirs(save_dir, exist_ok=True)
        self._load_all_state()

    def _load_all_state(self):
        for file in glob.glob(os.path.join(self.save_dir, "*.json")):
            user_id = os.path.split(file)[-1][:-5]
            with open(file, encoding="utf8") as f:
                self[user_id] = json.load(f)
            logger.info(f"恢复与{user_id}的{len(self[user_id])}条对话")

    def _dump_state(self, user_id: str):
        # Easy implement :)
        if user_id in self:
            with open(os.path.join(self.save_dir, f"{user_id}.json"), "w", encoding="utf8") as f:
                json.dump(self[user_id], f, ensure_ascii=False, indent=2)
        else:
            filename = os.path.join(self.save_dir, f"{user_id}.json")
            if os.path.exists(filename):
                os.remove(filename)

    def show_current_personality(self, user_id: str) -> Optional[str]:
        if self[user_id][0]["role"] == "system":
            prompt = self[user_id][0]["content"]

            for file in glob.glob(os.path.join("./personality", "*.json")):
                with open(file, encoding="utf8") as f:
                    if prompt == json.load(f)["content"]:
                        return os.path.split(file)[-1][:-5]

        return None

    @staticmethod
    def show_available_personalities() -> List[str]:
        personality_files = glob.glob(os.path.join("./personality", "*.json"))
        return [os.path.split(file)[-1][:-5] for file in personality_files]

    def init_dialog(self, user_id: str, personality: str = None, prompt: str = None):
        self[user_id] = []

        if personality is not None and prompt is not None:
            logger.error("[WARN] `personality`和`prompt`一个就够了！默认使用预定义的`personality`")

        if personality is not None:
            with open(os.path.join("personality", f"{personality}.json")) as f:
                personality_info: dict = json.load(f)
                self[user_id].append(personality_info)

        elif prompt is not None:
            self[user_id].append({"role": "system", "content": prompt})

        self._dump_state(user_id)

    def add_content(self, user_id: str, role: str, content: str):
        if role not in ("system", "user", "assistant"):
            logger.error(f"`role`必须为`system`，`user`和`assistant`之一，而不是'{role}'")
            return

        if user_id not in self:
            self.init_dialog(user_id)

        self[user_id].append({"role": role, "content": content})

        # Select and pop the first none-system content.
        target_role = "system"
        while num_tokens_from_messages(self[user_id]) >= self.dialog_max_length:
            idx = 0
            while idx < len(self[user_id]):
                if self[user_id][idx]["role"] != target_role:
                    break
                idx += 1

            if idx == len(self[user_id]):
                target_role = "user"
            else:
                popped_content = self[user_id].pop(idx)
                logger.warning(f"Length overflow ==> pop {popped_content}")

        self._dump_state(user_id)

    def delete_dialog(self, user_id: str):
        del self[user_id]
        self._dump_state(user_id)

    def reset_dialog(self, user_id: str):
        if self[user_id][0]["role"] != "system":
            self[user_id].clear()
        else:
            self[user_id] = self[user_id][:1]

        self._dump_state(user_id)

    def rollback_dialog(self, user_id: str, rollback_turns: int):
        dialog_length = len(self[user_id])
        if rollback_turns >= dialog_length:
            self[user_id] = []
        else:
            self[user_id] = self[user_id][:(dialog_length - rollback_turns)]

        self._dump_state(user_id)
