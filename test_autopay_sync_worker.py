from autopay_sync_worker import _amount, _digits, normalize, groq_compare


class Ref:
    def set(self, *args, **kwargs):
        raise AssertionError("teste não deve gravar no Firestore")


class Snapshot:
    id = "abc123"
    reference = Ref()

    def to_dict(self):
        return {
            "id": "TX9A8B7C",
            "amount": "1.000,00 MT",
            "body": "SMS AutoPay de teste",
            "sender_phone": "+258 84 123 4567",
            "sender_name": "Cliente Teste",
            "status": "pago",
        }


item = normalize(Snapshot())
assert item["id"] == "TX9A8B7C"
assert item["amount"] == 1000.0
assert item["sender_phone"] == "258841234567"
assert _digits("+258 84 123 4567") == "258841234567"
assert _amount("500,00 MT") == 500.0
assert groq_compare(item) == {"enabled": False, "matches_proof": None, "confidence": None}
print("AUTOPAY_WORKER_UNIT_TESTS_OK")
