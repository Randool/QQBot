"""
@File        :  config
@Contact     :  dlf43@qq.com
@Author      :  Randool
@Create Time :  2023/3/10
@Version     :  1.0
@Description :  None
"""
import json
from dataclasses import dataclass, field


@dataclass
class BotConfig:
    dialog_command: str = field(default="")
    cd_time: int = field(default=1)
    response_image: bool = field(default=False)

    api_key: str = field(default=None)
    default_personality: str = field(default="chatgpt")
    dialog_save_dir: str = field(default="./dialog_state")
    dialog_max_length: int = field(default=3000)

    @classmethod
    def from_config(cls, config_file: str):
        with open(config_file, encoding="utf8") as f:
            data = json.load(f)
        return cls(**data)
