from twilio.rest import Client
import time

class SMSClient():
    """Handles outbound messages"""
    def __init__(self, username, password, from_number, time_delay: float=0.5):
        self.client = Client(username, password)
        self.from_number = from_number
        self.time_delay = time_delay

    def send_sms(self, to, body):
        """Send one SMS using Twilio API"""
        return self.client.messages.create(
            from_=self.from_number,
            to=to, 
            body=body
        )

    def send_bulk(self, numbers, body):
        """Iterate over batch of numbers"""
        results = []

        for n in numbers:
            try:
                msg = self.send_sms(n, body)
                results.append((n, True, msg.sid))
            except Exception as e:
                results.append((n, False, str(e)))
            time.sleep(self.time_delay)

