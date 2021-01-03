from typing import Dict, Callable, Optional, Union

from yaml import YAMLObject, ScalarNode, MappingNode, add_multi_constructor, Loader
import re


class Output(YAMLObject):
    yaml_tag = '!Output'

    def __init__(self, output_text: str):
        self.output_text = output_text

    def run(self, output_func: Callable[[str], None]):
        output_func(self.output_text)

    @classmethod
    def from_yaml(cls, loader, node):
        return Output(node.value)


class Prompt(YAMLObject):
    yaml_tag = '!Prompt'

    def __init__(self, prompt: str, responses: Union[dict, str]):
        super().__init__()
        self.prompt = prompt
        self.responses = responses

    def run(self, prompt_func: Callable[[str], str]) -> Dict:
        key = self.prompt
        input_text = prompt_func(self.prompt)
        response = self._find_response(input_text)
        return {key: (input_text, response)}

    def _find_response(self, response):
        for key in self.responses:
            if re.search(key, response, re.IGNORECASE):
                return self.responses[key]


class Dialogue(YAMLObject):
    yaml_tag = '!Dialogue'

    def __init__(self, **conversations: dict):
        super().__init__()
        self.conversations = conversations

    def run(self, prompt_func: Callable[[str, int], str], output_func: Callable[[str], None]):
        return {
            key: self._resolve_conversation_value(value, prompt_func, output_func)
            for key, value
            in self.conversations.items()
        }

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
