class EvolutionMock:
    """Mock sem rede para observar chamadas feitas pelo backend."""

    def __init__(self):
        self.sent_text = []
        self.sent_media = []
        self.created_instances = []
        self.webhook_configs = []
        self.media_requests = []
        self.media_response = {"base64": ""}
        self.media_error = None

    def send_text(self, to, text, instance_name=None):
        self.sent_text.append({"to": to, "text": text, "instance_name": instance_name})
        return True

    def send_media(self, to, media, caption="", mediatype="image", filename="media.png", instance_name=None):
        self.sent_media.append({
            "to": to,
            "media": media,
            "caption": caption,
            "mediatype": mediatype,
            "filename": filename,
            "instance_name": instance_name,
        })
        return True

    def create_instance(self, phone_number, *args, **kwargs):
        self.created_instances.append({"phone_number": phone_number, "args": args, "kwargs": kwargs})
        return True

    def set_webhook(self, instance_name, config):
        self.webhook_configs.append({"instance_name": instance_name, "config": config})
        return {"status": 201}

    def transcribe_audio(self, payload, instance_name=None):
        self.media_requests.append({"payload": payload, "instance_name": instance_name})
        if self.media_error:
            raise self.media_error
        return self.media_response.get("text", "")
