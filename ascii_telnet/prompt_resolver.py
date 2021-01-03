import re
import time
from typing import Dict, Callable, Union

from yaml import YAMLObject

AVERAGE_READING_WORDS_PER_MINUTE = 250
AVERAGE_READING_WORDS_PER_SECOND = AVERAGE_READING_WORDS_PER_MINUTE / 60


class Output(YAMLObject):
    yaml_tag = '!Output'

    def __init__(self, output_text: str):
        self.output_text = output_text

    def run(self, output_func: Callable[[str], None]):
        output_func(self.output_text)
        words_in_output_text = len(self.output_text.split())
        seconds_to_sleep = words_in_output_text / AVERAGE_READING_WORDS_PER_SECOND + 2
        time.sleep(seconds_to_sleep)

    @classmethod
    def from_yaml(cls, loader, node):
        return Output(node.value)


class Prompt(YAMLObject):
    yaml_tag = '!Prompt'

    def __init__(self, prompt: str, response: Union[dict, str] = None):
        super().__init__()
        self.prompt = prompt
        self.response = response

    def run(self, prompt_func: Callable[[str], str]) -> Dict:
        key = self.prompt
        input_text = prompt_func(self.prompt)
        response = self._find_response(input_text)
        return {key: (input_text, response)}

    def _find_response(self, response):
        if isinstance(self.response, str):
            return response
        if isinstance(self.response, dict):
            for key in self.response:
                if re.search(key, response, re.IGNORECASE):
                    return self.response[key]


class Dialogue(YAMLObject):
    yaml_tag = '!Dialogue'

    def __init__(self, **conversations: dict):
        super().__init__()
        self.conversations = conversations

    def run(self, conversation_name: str, prompt_func: Callable[[str, int], str], output_func: Callable[[str], None]):
        return self._resolve_conversation_value(self.conversations[conversation_name], prompt_func, output_func)

    def _resolve_conversation_value(self, value, prompt_func: Callable[[str], str], output_func: Callable[[str], None]):
        if isinstance(value, Prompt):
            result_dict = value.run(prompt_func)
            dict_to_return = {}
            for key, input_response_tuple in result_dict.items():
                input_text, response = input_response_tuple
                resolved_value = self._resolve_conversation_value(response, prompt_func, output_func)
                dict_to_return['prompt'] = key
                dict_to_return['input'] = input_text
                dict_to_return['resolved'] = resolved_value
            return dict_to_return
        elif isinstance(value, Output):
            value.run(output_func)
            return None
        else:
            return value

    @classmethod
    def from_yaml(cls, loader, node):
        loaded = super(Dialogue, cls).from_yaml(loader, node)
        return loaded

    def __setstate__(self, state):
        self.conversations = state
