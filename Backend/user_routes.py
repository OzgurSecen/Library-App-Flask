
from flask import Blueprint, request, jsonify, current_app
from flask_bcrypt import Bcrypt
import uuid
from models import mysql
from config import SECRET_KEY
import jwt
import datetime

user_bp = Blueprint('user_bp', __name__)
bcrypt = Bcrypt()

@user_bp.route('/create', methods=['POST'])
def user_create():
    data = request.get_json()
    email = data['email']
    password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    role = data.get('role', 'user')
    user_uuid = str(uuid.uuid4())

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (uuid, email, password, role) VALUES (%s, %s, %s, %s)",
                (user_uuid, email, password, role))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Kullanıcı oluşturuldu', 'uuid': user_uuid})



@user_bp.route('/borrow', methods=['POST'])
def borrow_book():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token gerekli'}), 401
    try:
        decoded = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=['HS256'])
    except:
        return jsonify({'message': 'Token geçersiz'}), 403

    user_uuid = decoded['uuid']
    data = request.get_json()
    book_id = data.get('book_id')
    borrow_date = data.get('borrow_date')
    return_date = data.get('return_date')
    if not (book_id and borrow_date and return_date):
        return jsonify({'message': 'Eksik bilgi'}), 400

    cur = mysql.connection.cursor()
    # Kullanıcı id'sini bul
    cur.execute("SELECT id FROM users WHERE uuid=%s", (user_uuid,))
    user = cur.fetchone()
    if not user:
        cur.close()
        return jsonify({'message': 'Kullanıcı bulunamadı'}), 404
    user_id = user[0]

    # Kitap var mı kontrolü
    cur.execute("SELECT id FROM books WHERE id=%s", (book_id,))
    book = cur.fetchone()
    if not book:
        cur.close()
        return jsonify({'message': 'Kitap bulunamadı'}), 404

    # Aynı kitabı teslim etmeden tekrar başvuru engeli
    cur.execute("SELECT id, status FROM borrowed_books WHERE user_id=%s AND book_id=%s AND return_date >= CURDATE() AND status IN ('pending', 'approved')", (user_id, book_id))
    already_borrowed = cur.fetchone()
    if already_borrowed:
        if already_borrowed[1] == 'pending':
            cur.close()
            return jsonify({'message': 'Bu kitap için başvurunuz onay bekliyor.'}), 400
        else:
            cur.close()
            return jsonify({'message': 'Bu kitabı zaten ödünç aldınız ve henüz teslim etmediniz.'}), 400

    cur.execute("INSERT INTO borrowed_books (user_id, book_id, borrow_date, return_date, status) VALUES (%s, %s, %s, %s, 'pending')",
                (user_id, book_id, borrow_date, return_date))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Kitap başvurunuz alınmıştır, admin onayı bekleniyor.'})

@user_bp.route('/borrowed', methods=['GET'])
def get_borrowed_books():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token gerekli'}), 401
    try:
        decoded = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=['HS256'])
    except:
        return jsonify({'message': 'Token geçersiz'}), 403

    user_uuid = decoded['uuid']
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE uuid=%s", (user_uuid,))
    user = cur.fetchone()
    if not user:
        cur.close()
        return jsonify({'message': 'Kullanıcı bulunamadı'}), 404
    user_id = user[0]

    cur.execute("""
        SELECT b.id, b.title, b.category, b.pages, bb.borrow_date, bb.return_date, bb.status
        FROM borrowed_books bb
        JOIN books b ON bb.book_id = b.id
        WHERE bb.user_id = %s
        ORDER BY bb.borrow_date DESC
    """, (user_id,))
    borrowed = cur.fetchall()
    cur.close()

    status_map = {
        'pending': 'beklemede',
        'approved': 'onaylandı',
        'rejected': 'reddedildi'
    }
    result = [
        {
            'book_id': row[0],
            'title': row[1],
            'category': row[2],
            'pages': row[3],
            'borrow_date': row[4].isoformat(),
            'return_date': row[5].isoformat(),
            'status': status_map.get(row[6], row[6])
        } for row in borrowed
    ]
    return jsonify(result)


@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data['email']
    password = data['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT uuid, password, role FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()

    if not user:
        return jsonify({'message': 'Kullanıcı bulunamadı'}), 404

    if not bcrypt.check_password_hash(user[1], password):
        return jsonify({'message': 'Hatalı şifre'}), 401

    token = jwt.encode({
        'uuid': user[0],
        'role': user[2],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }, SECRET_KEY, algorithm='HS256')

    return jsonify({'token': token})

@user_bp.route('/update/<user_uuid>', methods=['PUT'])
def update_user(user_uuid):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token gerekli'}), 401

    try:
        decoded = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=['HS256'])
    except:
        return jsonify({'message': 'Token geçersiz'}), 403

    if decoded['uuid'] != user_uuid:
        return jsonify({'message': 'Sadece kendi hesabını güncelleyebilirsin'}), 403

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    cur = mysql.connection.scursor()
    if password:
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        cur.execute("UPDATE users SET email=%s, password=%s WHERE uuid=%s", (email, hashed, user_uuid))
    else:
        cur.execute("UPDATE users SET email=%s WHERE uuid=%s", (email, user_uuid))

    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Bilgiler güncellendi'})
