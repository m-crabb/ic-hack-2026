import deepl

class Translator():
    def __init__(self, auth_key: str):
        self.client = deepl.DeepLClient(auth_key)

    def translate(self, message: str, target_lang: str='DE'):
        res = self.client.translate_text(message, target_lang=target_lang)
        translation = ""
        for r in res:
            translation += r.text + '\n'
        return translation