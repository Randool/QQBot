"""
@File        :  chatgpt
@Contact     :  dlf43@qq.com
@Author      :  Randool
@Create Time :  2023/3/9
@Version     :  1.0
@Description :  None
"""
import json
from dataclasses import dataclass
from typing import List, Optional

import openai
import tiktoken
from nonebot.log import logger

from web_api import query_web_api


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


@dataclass
class ChatCompletionArgs:
    model: str = "gpt-3.5-turbo"
    temperature: float = 1.0
    top_p: float = 1.0
    n: int = 1
    max_tokens: int = int(1e4)


_DEFAULT_ARGS = ChatCompletionArgs()


class ChatGPT:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    @staticmethod
    def interact_chatgpt(
            messages: List[dict], chat_completion_args: ChatCompletionArgs = _DEFAULT_ARGS,
            timeout=20, timeout_retry=1,
    ) -> Optional[dict]:
        """ See: https://platform.openai.com/docs/guides/chat/introduction """
        # [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {"role": "user", "content": "Who won the world series in 2020?"},
        #     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        #     {"role": "user", "content": "Where was it played?"}
        # ]
        response = None

        while response is None and timeout_retry > 0:
            timeout_retry -= 1
            try:
                response = openai.ChatCompletion.create(
                    messages=messages,
                    **vars(chat_completion_args),
                    timeout=timeout,
                )
                break
            except openai.error.Timeout:
                logger.error("`openai.error.Timeout`，重新尝试！")

        if response is not None:
            response_message = dict(response["choices"][0]["message"])
            return response_message

        return None

    @staticmethod
    def interact_chatgpt_api(
            messages: List[dict], chat_completion_args: ChatCompletionArgs = _DEFAULT_ARGS,
            timeout=20, timeout_retry=1,
    ):
        """ 这个插件会更具模型自己的选择多次调用api """
        response = None

        while response is None and timeout_retry > 0:
            timeout_retry -= 1
            try:
                response = openai.ChatCompletion.create(
                    messages=messages,
                    **vars(chat_completion_args),
                    timeout=timeout,
                )
                break
            except openai.error.Timeout:
                logger.error("`openai.error.Timeout`，重新尝试！")

        if response is not None:
            response_message = dict(response["choices"][0]["message"])
            try:
                # {"calls": [{"API": "Google", "query": "What other name is Coca-Cola known by?"},{"API": "Google", "query": "Who manufactures Coca-Cola?"}]}
                APIs: List[dict] = json.loads(response_message["content"])["calls"]
            except (json.JSONDecodeError, KeyError):  # 常规回复或者是异常结果，则直接返回
                return response_message
            else:
                # TODO: 依次调用API
                results = []
                for API in APIs:
                    try:
                        api_name = API["API"]
                        query = API["query"]
                        results_ = query_web_api(api_name, query)
                    except KeyError:
                        logger.warning(f"Incomplete API: {API}")
                        continue
                    else:
                        results.extend(results_)
                        logger.info(f"[{api_name}] {results_}")

                # TODO: 构造prompt
                prompt = ""

        return None
