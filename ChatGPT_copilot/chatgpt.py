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
    max_tokens: int = int(1e3)


_DEFAULT_ARGS = ChatCompletionArgs()


class ChatGPT:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    @staticmethod
    def _auto_retry_completion(completion_args: dict, timeout=30, timeout_retry=1):
        """ `completion_args` should contain at least `message` """
        response = None

        while response is None and timeout_retry > 0:
            timeout_retry -= 1
            try:
                response = openai.ChatCompletion.create(**completion_args, timeout=timeout)
                break
            except openai.error.Timeout:
                logger.error("`openai.error.Timeout`，重新尝试！")

        return response  # response["choices"][0]["message"]

    @staticmethod
    async def interact_chatgpt(
            messages: List[dict], chat_completion_args: ChatCompletionArgs = _DEFAULT_ARGS,
            timeout=30, timeout_retry=1,
    ) -> Optional[dict]:
        """ See: https://platform.openai.com/docs/guides/chat/introduction """
        # [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {"role": "user", "content": "Who won the world series in 2020?"},
        #     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        #     {"role": "user", "content": "Where was it played?"}
        # ]
        response = ChatGPT._auto_retry_completion(
            completion_args={"messages": messages, **vars(chat_completion_args)},
            timeout=timeout, timeout_retry=timeout_retry,
        )

        if response is not None:
            response_message = dict(response["choices"][0]["message"])
            return response_message

        return None

    @staticmethod
    async def interact_chatgpt_pro(
            messages: List[dict], chat_completion_args: ChatCompletionArgs = _DEFAULT_ARGS,
            timeout=20, timeout_retry=2, secret_keys: dict = None,
    ):
        """ See: https://platform.openai.com/docs/guides/chat/introduction """
        # [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {"role": "user", "content": "Who won the world series in 2020?"},
        #     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        #     {"role": "user", "content": "Where was it played?"}
        # ]
        response = ChatGPT._auto_retry_completion(
            completion_args={"messages": messages, **vars(chat_completion_args)},
            timeout=timeout, timeout_retry=timeout_retry,
        )

        if response is not None:
            response_message = dict(response["choices"][0]["message"])
            try:
                # {"calls": [
                #   {"API": "Google", "query": "What other name is Coca-Cola known by?"},
                #   {"API": "Google", "query": "Who manufactures Coca-Cola?"}
                # ]}
                APIs: List[dict] = json.loads(response_message["content"])["calls"]
            except (json.JSONDecodeError, KeyError):
                # Normal reply or abnormal result is returned directly
                return response_message

            # Call API sequentially
            search_results = []
            secret_keys = {} if secret_keys is None else secret_keys

            for API in APIs:
                try:
                    api_name = API["API"]
                    query = API["query"]
                    results = query_web_api(api_name, query, **secret_keys)
                except KeyError:
                    logger.warning(f"Incomplete API: {API}")
                    continue
                else:
                    search_results.extend(results)
                    logger.info(f"[{api_name}] {results}")

            # Construct prompt
            prefix = "Web search results: "
            suffix = f"Instructions: Using the provided web search results, write a " \
                     f"comprehensive and summarized reply to the given query. The " \
                     f"language used should be consistent with the query. The reply " \
                     f"should let ChatGPT understand easily and fastly."
            query = messages[-1]["content"]
            prompt = prefix + str(search_results) + suffix + "Query: " + query
            logger.info(f"[API prompt] {prompt}")

            response2 = ChatGPT._auto_retry_completion(
                completion_args={"messages": [{"role": "user", "content": prompt}], **vars(chat_completion_args)},
                timeout=timeout, timeout_retry=timeout_retry,
            )

            if response2 is not None:
                response_message2 = dict(response2["choices"][0]["message"])
                return response_message2

        return None
