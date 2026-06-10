from flask import Flask
from flask_cors import CORS
from app.api.endpoints import api_bp
from app.models.database import init_db

app = Flask(__name__)

CORS(app)
init_db(app)

# 블루프린트 등록
app.register_blueprint(api_bp, url_prefix="/api")
