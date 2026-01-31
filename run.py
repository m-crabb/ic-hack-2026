"""Demo: run AgriGuard for a location (city or lat/lon). Loads .env from project root."""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from agriguard import AgriGuard
from translate import Translator
from outbound import SMSClient

if __name__ == "__main__":
    DEEPL_TOKEN = os.environ.get("DEEPL_TOKEN")
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER')
    TWILIO_TO_NUMBER = os.environ.get('TWILIO_TO_NUMBER')

    # Option 1: by city name
    app = AgriGuard(city_name="London")
    translator = Translator(DEEPL_TOKEN)
    smsclient = SMSClient(
        TWILIO_ACCOUNT_SID, 
        TWILIO_AUTH_TOKEN, 
        TWILIO_FROM_NUMBER
    )
    

    # Option 2: by latitude / longitude (e.g. Berlin)
    # app = AgriGuard(latitude=52.52, longitude=13.41)

    if app.lat is not None:
        advice = app.get_ai_agri_advice()
        app.print_display(advice)
        tl = translator.translate(advice)
        print(tl)
        smsclient.send_sms(TWILIO_TO_NUMBER, tl)



