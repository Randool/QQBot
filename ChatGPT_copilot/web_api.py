import re
import urllib.parse
from typing import List

import openai
import requests


class MetaAPI:
    @staticmethod
    def call(query: str, **kwargs):
        pass


class WikiSearchAPI(MetaAPI):
    api_name = 'WikiSearch'
    base_url = 'https://en.wikipedia.org/w/api.php'

    @staticmethod
    def call(query, num_results=2) -> List[str]:
        def remove_html_tags(text):
            return re.sub(re.compile('<.*?>'), '', text)

        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
        }
        call_url = WikiSearchAPI.base_url + urllib.parse.urlencode(params)
        r = requests.get(call_url)

        data = r.json()['query']['search']
        data = [d['title'] + ": " + remove_html_tags(d["snippet"]) for d in data][:num_results]
        # print()
        return data


class GoogleSearchAPI(MetaAPI):
    api_name = 'GoogleSearch'
    base_url = 'https://customsearch.googleapis.com/customsearch/v1?'

    @staticmethod
    def call(query, num_results=2):
        params = {
            'q': query,
            'key': 'YOUR_GOOGLE_API_KEY',
            'cx': 'YOUR_GOOGLE_CLIENT_ID',
            'c2coff': '0',
            'num': num_results
        }

        call_url = GoogleSearchAPI.base_url + urllib.parse.urlencode(params)
        r = requests.get(call_url)
        if "items" in r.json():
            items = r.json()["items"]
            filter_data = [
                item["title"] + ": " + item["snippet"] for item in items
            ]
            # print(filter_data)
            return filter_data
        else:
            return []


class WolframAPI(MetaAPI):
    api_name = 'Wolfram'
    base_url = 'https://api.wolframalpha.com/v2/query'

    @staticmethod
    def call(query, num_results=3):
        query = query.replace('+', ' plus ')

        params = {
            'input': query,
            'format': 'plaintext',
            'output': 'JSON',
            'appid': 'YOUR_WOLFRAMALPHA_API_ID',  # get from wolfram Alpha document
        }
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }

        responseFromWolfram = requests.get(WolframAPI.base_url, params=params, headers=headers)
        pods = responseFromWolfram.json()['queryresult']['pods'][:num_results]
        pods_id = [pod["id"] for pod in pods]
        subplots = [(pod['subpods']) for pod in pods]
        pods_plaintext = []
        for subplot in subplots:
            text = '\n'.join([c['plaintext'] for c in subplot])
            pods_plaintext.append(text)
        # pods_plaintext = ['\n'.join(pod['subpods']['plaintext']) for pod in pods]
        res = [pods_id[i] + ": " + pods_plaintext[i] for i in range(len(pods_plaintext)) if
               pods_plaintext[i].strip() != '']
        return res


class GPT3API:
    api_name = 'GPT3'
    model_name = {
        'tiny': 'text-ada-001',
        'small': 'text-babbage-001',
        'middle': 'text-curie-001',
        'large': "text-davinci-003",
    }

    @staticmethod
    def call(query: str, search_result, model_type='text-curie-001'):
        if openai.api_key is None:
            raise RuntimeError("Set openai.api_key first")

        prefix = "Web search results:"
        num_words = 100
        suffix = f"instructions: Using the provided web search " \
                 f"results, write a comprehensive and summarized reply to the given query in {num_words} words and in " \
                 f"English. The reply should let ChatGPT understand easily and fastly."
        if not search_result:
            return ''
        prompt = prefix + str(search_result) + suffix + "Query:" + query
        # print(query)
        # print(prompt)
        res = openai.Completion.create(
            model=model_type,
            prompt=prompt,
            temperature=0,
            max_tokens=500
        )

        text = res.get('choices')[0].get("text").strip()
        # all_texts = [c.get("text").strip() for c in res.get('choices')]
        # print(all_texts)
        # json_res = json.dumps(res, ensure_ascii=False)
        # print(json_res)
        return text


_APIs = [WikiSearchAPI, GoogleSearchAPI, WolframAPI]

REGISTERED_API = {_api.api_name: _api for _api in _APIs}


def query_web_api(api_name: str, query: str, num_results: int = 2) -> List[str]:
    API = REGISTERED_API.get(api_name, None)
    if API is None:
        raise KeyError(f"No such api_name: {api_name}")
    return API.call(query, num_results)
