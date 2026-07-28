from flask import Blueprint

web_bp = Blueprint('web_bp', __name__)

@web_bp.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático está online! 🚀", 200
