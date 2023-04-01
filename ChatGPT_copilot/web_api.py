import re
import urllib.parse
from typing import List, Optional

import openai
import requests
import wolframalpha


class MetaAPI:
    @staticmethod
    def call(*args, **kwargs) -> List[str]:
        pass


class WikiSearchAPI(MetaAPI):
    api_name = 'WikiSearch'
    base_url = 'https://en.wikipedia.org/w/api.php'

    @staticmethod
    def call(query: str, num_results: int = 4, **kwargs) -> List[str]:
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
    def call(query: str, google_key: str, google_cx: str, num_results: int = 3, **kwargs) -> List[str]:
        params = {
            'key': google_key,
            'q': query,
            'cx': google_cx,
            'start': '0',
            'num': num_results
        }

        # call_url = GoogleSearchAPI.base_url + urllib.parse.urlencode(params)
        r = requests.get(GoogleSearchAPI.base_url, params=params)
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
    def call(query: str, wolfram_appid: str, num_results: int = 5, **kwargs) -> List[str]:
        client = wolframalpha.Client(app_id=wolfram_appid)
        response = client.query(query)
        results = []

        if response["@success"]:
            for i, pod in enumerate(response.pods):
                if i == num_results:
                    break
                text = '\n'.join(pod.texts)
                results.append(f"{pod.id}: {text}")

        return results


_APIs = [WikiSearchAPI, GoogleSearchAPI, WolframAPI]
REGISTERED_API = {_api.api_name: _api for _api in _APIs}


def query_web_api(api_name: str, query: str, num_results: Optional[int] = None, **kwargs) -> List[str]:
    API = REGISTERED_API.get(api_name, None)
    if API is None:
        raise KeyError(f"No such api_name: {api_name}")
    kwargs = {"query": query, **kwargs}
    if num_results is not None:
        kwargs["num_results"] = num_results
    return API.call(**kwargs)


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
