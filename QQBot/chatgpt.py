"""
@File        :  chatgpt
@Contact     :  dlf43@qq.com
@Author      :  Randool
@Create Time :  2023/3/9
@Version     :  1.0
@Description :  None
"""
import json
import re
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
            except openai.error.RateLimitError as e:
                logger.error(f"`openai.error.RateLimitError`, {e}")

        return response  # response["choices"][0]["message"]

    @staticmethod
    async def interact_chatgpt(
            messages: List[dict], chat_completion_args: ChatCompletionArgs = _DEFAULT_ARGS,
            timeout=20, timeout_retry=2, secret_keys: dict = None,
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
        response_message = dict(response["choices"][0]["message"])
        return response_message

    @staticmethod
    def _summarize_dialog(messages: List[dict]) -> str:
        """ Converting dialog in dict format into a string. """
        # TODO: 引入对话历史总结
        return "\n".join(f"{m['role']}:{m['content']}" for m in messages)

    @staticmethod
    def _call_plugin_apis(plugin_APIs: List[dict], secret_keys: dict = None) -> List[str]:
        search_results: List[str] = []

        for API in plugin_APIs:
            try:
                plugin_name, query = API["API"], API["query"]
                results = query_web_api(plugin_name, query, **({} if secret_keys is None else secret_keys))
            except KeyError:
                logger.warning(f"Incomplete API: {API}")
                continue
            else:
                search_results.extend(results)
                logger.info(f"[{plugin_name}] {results}")

        return search_results

    @staticmethod
    async def interact_chatgpt_with_plugins(
            messages: List[dict], chat_completion_args: ChatCompletionArgs = _DEFAULT_ARGS,
            timeout=20, timeout_retry=2, secret_keys: dict = None,
    ) -> Optional[dict]:
        """ Enable the large model to access external knowledge and tools. """
        logger.info("[interact_chatgpt_with_plugins called]")

        ### 0x00: Summarize the dialog
        summarized_dialog = ChatGPT._summarize_dialog(messages)

        ### 0x01: Generate plugin calls
        with open("personality/plugin/2_generate_plugin_calls.txt", encoding="utf8") as f:
            plugin_prompt = f.read()
            plugin_prompt = plugin_prompt.replace("{{dialog_history}}", summarized_dialog)

        response = ChatGPT._auto_retry_completion(
            completion_args={"messages": [{"role": "user", "content": plugin_prompt}], **vars(chat_completion_args)},
            timeout=timeout, timeout_retry=timeout_retry,
        )

        if response is None:
            return None

        response_message = dict(response["choices"][0]["message"])
        try:
            # [{"API": "Google", "query": "What other name is Coca-Cola known by?"}]
            APIs_str = response_message["content"]
            APIs_str = re.search(r"\[.*]", APIs_str).group()
            APIs: List[dict] = json.loads(APIs_str)
            logger.info(f"[API] {APIs}")
        except (json.JSONDecodeError, KeyError, AttributeError):
            # Normal reply or abnormal result is returned directly
            return response_message

        ### 0x02: Call APIs sequentially  TODO: 并发调用API
        search_results = ChatGPT._call_plugin_apis(APIs, secret_keys)

        ### 0x03. Generate reply based on the dialog history and the results of plugins
        with open("personality/plugin/3_generate_reply.txt", encoding="utf8") as f:
            reply_prompt = f.read()
            reply_prompt = reply_prompt.replace("{{dialog_history}}", summarized_dialog)
            reply_prompt = reply_prompt.replace("{{knowledge}}", "\n\n".join(search_results))

        response2 = ChatGPT._auto_retry_completion(
            completion_args={"messages": [{"role": "user", "content": reply_prompt}], **vars(chat_completion_args)},
            timeout=timeout, timeout_retry=timeout_retry,
        )

        if response2 is None:
            return None

        response_message = dict(response2["choices"][0]["message"])

        return response_message