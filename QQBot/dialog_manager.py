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
    """
    {
        user_id: {
            "personality": "xxx",
            "dialog": [{"role": "", "content": ""}, ...]
        }
    }
    """

    def __init__(self, save_dir: str, dialog_max_length: int = 4000, default_personality: str = "chatgpt"):
        super().__init__(lambda: {"personality": default_personality, "dialog": []})
        self.save_dir = save_dir
        self.dialog_max_length = dialog_max_length

        os.makedirs(save_dir, exist_ok=True)
        self._load_all_state()

    def _load_all_state(self):
        for file in sorted(glob.glob(os.path.join(self.save_dir, "*.json"))):
            user_id = os.path.split(file)[-1][:-5]
            with open(file, encoding="utf8") as f:
                self[user_id] = json.load(f)
            logger.info(f"恢复与{user_id}的{len(self[user_id]['dialog'])}条对话")

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
        personality = self[user_id]["personality"]
        self._dump_state(user_id)
        return personality

    @staticmethod
    def show_available_personalities() -> List[str]:
        personality_files = glob.glob(os.path.join("./personality", "*"))
        return [os.path.split(file)[-1] for file in personality_files]

    def checkout_personality(self, user_id: str, personality: str = None):
        """
        :param user_id:         User ID
        :param personality:     目标人格，如果为None则创建空列表
        """
        logger.info(f"[user_id: {user_id}] [人格: {personality}]")

        current_user = self[user_id]

        if personality is not None:
            current_user["personality"] = personality
            current_user["dialog"] = []

            if (p_file := os.path.join("personality", f"{personality}")) and not os.path.isdir(p_file):
                # Plugin personality will clear current system prompt
                with open(p_file, encoding="utf8") as f:
                    personality_info: dict = {"role": "system", "content": f.read()}

                current_user["dialog"].insert(0, personality_info)

        self._dump_state(user_id)

    def add_content(self, user_id: str, role: str, content: str):
        current_user = self[user_id]

        if role not in ("system", "user", "assistant"):
            logger.error(f"`role`必须为`system`，`user`和`assistant`之一，而不是'{role}'")
            return

        if user_id not in self:
            self.checkout_personality(user_id)

        current_user["dialog"].append({"role": role, "content": content})

        # Select and pop the first none-system content.
        target_role = "system"
        while num_tokens_from_messages(current_user["dialog"]) >= self.dialog_max_length:
            idx = 0
            while idx < len(current_user["dialog"]):
                if current_user["dialog"][idx]["role"] != target_role:
                    break
                idx += 1

            if idx == len(current_user["dialog"]):
                target_role = "user"
            else:
                popped_content = current_user["dialog"].pop(idx)
                logger.warning(f"Length overflow ==> pop {popped_content}")

        self._dump_state(user_id)

    def delete_dialog(self, user_id: str):
        del self[user_id]
        self._dump_state(user_id)

    def reset_dialog(self, user_id: str):
        current_user = self[user_id]
        current_user_dialog: List[dict] = current_user["dialog"]

        if len(current_user_dialog) > 0:
            if current_user_dialog[0]["role"] == "system":
                current_user["dialog"] = current_user["dialog"][:1]
            else:
                current_user_dialog.clear()

        self._dump_state(user_id)

    def rollback_dialog(self, user_id: str, rollback_turns: int):
        current_user = self[user_id]

        dialog_length = len(current_user["dialog"])
        if rollback_turns >= dialog_length:
            current_user["dialog"] = []
        else:
            current_user["dialog"] = current_user["dialog"][:(dialog_length - rollback_turns)]

        self._dump_state(user_id)
