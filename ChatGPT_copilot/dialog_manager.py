"""
@File        :  dialog_manager
@Contact     :  dlf43@qq.com
@Author      :  Randool
@Create Time :  2023/3/31
@Version     :  1.0
@Description :  None
"""
import glob
import json
import os
from collections import defaultdict
from typing import List, Optional

from nonebot.log import logger

from chatgpt import num_tokens_from_messages


class DialogManager(defaultdict):
    """ user_id ==> [{"role": "", "content": ""}, ...] """

    def __init__(self, save_dir: str, dialog_max_length: int = 3000):
        super().__init__(list)
        self.save_dir = save_dir
        self.dialog_max_length = dialog_max_length

        os.makedirs(save_dir, exist_ok=True)
        self._load_all_state()

    def _load_all_state(self):
        for file in sorted(glob.glob(os.path.join(self.save_dir, "*.json"))):
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
        if len(self[user_id]) > 0 and self[user_id][0]["role"] == "system":
            prompt = self[user_id][0]["content"]

            for file in glob.glob(os.path.join("./personality", "*")):
                with open(file, encoding="utf8") as f:
                    if prompt == f.read():
                        return os.path.split(file)[-1]

        return None

    @staticmethod
    def show_available_personalities() -> List[str]:
        personality_files = glob.glob(os.path.join("./personality", "*"))
        return [os.path.split(file)[-1] for file in personality_files]

    def checkout_personality(self, user_id: str, personality: str = None, reset: bool = False):
        """
        :param user_id:         User ID
        :param personality:     目标人格，如果为None则创建空列表
        :param reset:           True则重置对话历史
        """
        logger.info(f"[user_id: {user_id}] [人格: {personality}] [重置：{reset}]")

        if personality is not None:
            with open(os.path.join("personality", f"{personality}")) as f:
                personality_info: dict = {"role": "system", "content": f.read()}

            if len(self[user_id]) == 0 or self[user_id][0]["role"] != "system":
                self[user_id].insert(0, personality_info)
            else:
                self[user_id][0] = personality_info

        if reset and len(self[user_id]) > 0:
            if self[user_id][0]["role"] != "system":
                self[user_id] = []
            else:
                self[user_id] = self[user_id][:1]

        self._dump_state(user_id)

    def add_content(self, user_id: str, role: str, content: str):
        if role not in ("system", "user", "assistant"):
            logger.error(f"`role`必须为`system`，`user`和`assistant`之一，而不是'{role}'")
            return

        if user_id not in self:
            self.checkout_personality(user_id)

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
