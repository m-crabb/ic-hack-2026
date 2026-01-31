import deepl

class Translator():
    def __init__(self, auth_key: str):
        self.client = deepl.DeepLClient(auth_key)

    def translate(self, message: str, target_lang: str):
        return self.client.translate_text(message, target_lang)