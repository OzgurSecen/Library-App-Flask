# book_routes.py

from flask import Blueprint, jsonify
from models import mysql

book_bp = Blueprint('book_bp', __name__)

@book_bp.route('/book/all', methods=['GET'])
def get_books():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, title, category, pages FROM books")
    books = cur.fetchall()
    cur.close()

    return jsonify([{'id': b[0], 'title': b[1], 'category': b[2], 'pages': b[3]} for b in books])
