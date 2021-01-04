import re
from typing import Dict, Callable, Union

from yaml import YAMLObject


class Output(YAMLObject):
    yaml_tag = '!Output'

    def __init__(self, output_text: str):
        self.output_text = output_text

    def run(self, output_func: Callable[[str], None]):
        output_func('\n' + self.output_text)

    @classmethod
    def from_yaml(cls, loader, node):
        return Output(node.value)


class Repeat(YAMLObject):
    yaml_tag = '!Repeat'

    @classmethod
    def from_yaml(cls, loader, node):
        return cls()


class Prompt(YAMLObject):
    yaml_tag = '!Prompt'

    def __init__(self, prompt: str, response: Union[dict, str, Output], default: Union[str, Output] = None):
        super().__init__()
        self.prompt = prompt
        self.response = response
        self.default = default

    def run(self, prompt_func: Callable[[str], str]) -> Dict:
        key = self.prompt
        input_text = prompt_func('\n' + self.prompt + '\n>> ')
        response = self._find_response(input_text)
        if isinstance(response, Repeat):
            return self.run(prompt_func)
        return {key: (input_text, response)}

    def _find_response(self, response):
        if isinstance(self.response, (str, Output, Prompt)):
            return self.response
        if isinstance(self.response, dict):
            for key in self.response:
                if re.search(key, response, re.IGNORECASE):
                    return self.response[key]
        return self.default

    def __setstate__(self, state):
        self.__init__(**state)


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
            return {
                "output": value.output_text
            }
        else:
            return value

    @classmethod
    def from_yaml(cls, loader, node):
        loaded = super(Dialogue, cls).from_yaml(loader, node)
        return loaded

    def __setstate__(self, state):
        self.conversations = state
