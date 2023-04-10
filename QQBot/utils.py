"""
@File        :  utils
@Contact     :  dlf43@qq.com
@Author      :  Randool
@Create Time :  2023/3/9
@Version     :  1.0
@Description :  None
"""
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Type, Union

from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import GROUP, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends
from nonebot.rule import to_me


def create_matcher(
        command: Union[str, List[str]],
        only_to_me: bool = True,
        private: bool = True,
        priority: int = 999,
        block: bool = True,
) -> Type[Matcher]:
    params: Dict[str, Any] = {
        "priority": priority,
        "block": block,
    }

    if command:
        on_matcher = on_command
        command = [command] if isinstance(command, str) else command
        params["cmd"] = command.pop(0)
        params["aliases"] = set(command)
    else:
        on_matcher = on_message

    if only_to_me:
        params["rule"] = to_me()

    if not private:
        params["permission"] = GROUP

    return on_matcher(**params)


def cooldown_checker(cd_time: int) -> Any:
    cooldown = defaultdict(int)

    async def check_cooldown(
            matcher: Matcher, event: MessageEvent
    ) -> AsyncGenerator[None, None]:
        cooldown_time = cooldown[event.user_id] + cd_time
        if event.time < cooldown_time:
            await matcher.finish(
                f"ChatGPT 冷却中，剩余 {cooldown_time - event.time} 秒", at_sender=True
            )
        yield
        cooldown[event.user_id] = event.time

    return Depends(check_cooldown)
