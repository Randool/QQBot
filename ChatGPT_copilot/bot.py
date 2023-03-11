import re

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as V11_Adapter
from nonebot.adapters.onebot.v11 import MessageEvent as V11_MessageEvent
from nonebot.log import logger
from nonebot.typing import T_State

from chatgpt import ChatGPT, DialogManager
from config import BotConfig
from utils import cooldown_checker, create_matcher

nonebot.init()
nonebot.load_from_toml("pyproject.toml")

driver = nonebot.get_driver()
driver.register_adapter(V11_Adapter)

config = BotConfig.from_config("config.json")

# ChatGPT & Dialog manager
bot = ChatGPT(config.api_key)
dialog_manager = DialogManager(config.dialog_save_dir, config.dialog_max_length)

# Matchers
help_matcher = create_matcher(command="help", priority=1)
checkout_matcher = create_matcher(command="checkout", priority=1)
refresh_matcher = create_matcher(command="reset", priority=1)
rollback_matcher = create_matcher(command="rollback", priority=1)
chat_matcher = create_matcher(command=config.dialog_command, priority=999)

_HELP = """帮助：
- /help：显示帮助文档
- /checkout <人格:str>：切换不同的人格模板（该操作会重置对话历史）
- /reset：重置对话历史
- /rollback <n:int>：将当前对话回滚n条
"""


@help_matcher.handle()
async def _show_help(_event: V11_MessageEvent, _state: T_State):
    await help_matcher.send(_HELP, at_sender=True)


@checkout_matcher.handle()
async def _checkout_personality(event: V11_MessageEvent, state: T_State):
    user_id = event.get_user_id()
    message = event.get_message()
    content = message.extract_plain_text().strip()
    available_personalities = dialog_manager.show_available_personalities()

    if re.match(r"/checkout\s+\w+", content):
        personality = content.split()[1]
        if personality not in available_personalities:
            await rollback_matcher.send(f"人格不在列表中，当前可用人格：{available_personalities}", at_sender=True)
        else:
            dialog_manager.init_dialog(user_id, personality)
            await rollback_matcher.send(f"人格：“{personality}”切换成功", at_sender=True)
    else:
        await rollback_matcher.send("指令格式错误，应当为“/checkout <人格:str>”。"
                                    f"当前可用人格：{available_personalities}", at_sender=True)


@refresh_matcher.handle()
async def _refresh_matcher(event: V11_MessageEvent, state: T_State):
    user_id = event.get_user_id()
    dialog_manager.reset_dialog(user_id)
    logger.info(f"重置与{user_id}的对话")
    await refresh_matcher.send("重置对话成功", at_sender=True)


@rollback_matcher.handle()
async def _rollback_matcher(event: V11_MessageEvent, state: T_State):
    logger.info(str(event.__dict__))

    user_id = event.get_user_id()
    message = event.get_message()
    content = message.extract_plain_text().strip()

    if re.match(r"/rollback\s+\d+", content):
        n = int(content.split()[1])
        dialog_manager.rollback_dialog(user_id, n)
        logger.info(f"回滚与{user_id}的对话{n}条")
        await rollback_matcher.send("回滚成功", at_sender=True)
    else:
        await rollback_matcher.send("指令格式错误，应当为“/rollback <n:int>”", at_sender=True)


@chat_matcher.handle(parameterless=[cooldown_checker(config.cd_time)])
async def _chat_matcher(event: V11_MessageEvent, state: T_State):
    user_id = event.get_user_id()
    message = event.get_message()
    content = message.extract_plain_text().strip()

    # await chat_matcher.send("啊对对对", at_sender=True)

    if user_id not in dialog_manager:
        logger.info(f"[赋予人格]：{config.default_personality}")
        dialog_manager.init_dialog(user_id, personality=config.default_personality)

    dialog_manager.add_content(user_id, "user", content)

    response = bot.interact_chatgpt(dialog_manager[user_id])
    response["content"] = response["content"].strip()

    logger.info(f"[回复]：{response}")
    dialog_manager.add_content(user_id, **response)

    await chat_matcher.send(response["content"], at_sender=True)


if __name__ == "__main__":
    logger.info(str(driver.config))
    nonebot.run()
