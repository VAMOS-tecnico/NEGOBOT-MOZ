#### `app.py`
```python
from flask import Flask
from config import configure_app
from routes import register_routes
from services import init_services, get_db, send_whatsapp
from executor import start_executor
from executor import _init_firebase as _init_executor_firebase
import threading

def create_app():
    app = Flask(__name__)
    configure_app(app)
    register_routes(app)

    # Inicializa serviços (Firebase, etc.)
    init_services()

    # Inicia executor como processo separado se preferires (opcional)
    # Recomendo executar executor.py como worker separado em produção.
    # Se quiseres iniciar aqui para testes locais, descomenta:
    # threading.Thread(target=start_executor, daemon=True).start()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(app.config.get("PORT", 5000)))
