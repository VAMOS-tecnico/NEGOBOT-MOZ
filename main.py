from app import create_app

app = create_app()

# Para WSGI servers (gunicorn): `gunicorn main:app`
