from flask import Flask
from flask_cors import CORS
from config import *
from models import mysql, init_db, create_tables
from user_routes import user_bp
from book_routes import book_bp
from admin_routes import admin_bp

app = Flask(__name__)
CORS(app)

# Veritabanı Ayarları
app.config['MYSQL_HOST'] = MYSQL_HOST
app.config['MYSQL_USER'] = MYSQL_USER
app.config['MYSQL_PASSWORD'] = MYSQL_PASSWORD
app.config['MYSQL_DB'] = MYSQL_DB
app.config['SECRET_KEY'] = SECRET_KEY

# DB Başlat
init_db(app)

@app.before_request
def setup():
    create_tables()


# Blueprint'leri ekle
app.register_blueprint(user_bp, url_prefix='/uygulama/api/user')
app.register_blueprint(book_bp, url_prefix='/uygulama/api/book')
app.register_blueprint(admin_bp, url_prefix='/uygulama/api/admin')

print("Flask başlatılıyor...")

if __name__ == '__main__':
    print("Flask çalışıyor...")
    app.run(debug=True)
