
# admin_routes.py
from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from models import mysql
from config import SECRET_KEY
import jwt
import uuid

admin_bp = Blueprint('admin_bp', __name__)
bcrypt = Bcrypt()


def admin_required(func):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token gerekli'}), 401
        try:
            decoded = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=['HS256'])
        except:
            return jsonify({'message': 'Geçersiz token'}), 403

        if decoded['role'] != 'admin':
            return jsonify({'message': 'Admin yetkisi gerekli'}), 403
        request.user = decoded
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# Tüm ödünç başvurularını listele (admin)
@admin_bp.route('/borrowed/all', methods=['GET'])
@admin_required
def get_all_borrowed():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT bb.id, u.email, b.title, bb.borrow_date, bb.return_date, bb.status
        FROM borrowed_books bb
        JOIN users u ON bb.user_id = u.id
        JOIN books b ON bb.book_id = b.id
        ORDER BY bb.status, bb.borrow_date DESC
    """)
    borrowed = cur.fetchall()
    cur.close()
    result = [
        {
            'borrow_id': row[0],
            'user_email': row[1],
            'book_title': row[2],
            'borrow_date': row[3].isoformat(),
            'return_date': row[4].isoformat(),
            'status': row[5]
        } for row in borrowed
    ]
    return jsonify(result)

# Admin ödünç başvurusunu onaylar
@admin_bp.route('/borrowed/approve/<int:borrow_id>', methods=['POST'])
@admin_required
def approve_borrow(borrow_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT status FROM borrowed_books WHERE id=%s", (borrow_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'message': 'Başvuru bulunamadı'}), 404
    if row[0] != 'pending':
        cur.close()
        return jsonify({'message': 'Başvuru zaten onaylanmış veya reddedilmiş'}), 400
    cur.execute("UPDATE borrowed_books SET status='approved' WHERE id=%s", (borrow_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Başvuru onaylandı, kitap ödünç alındı.'})

# Admin ödünç başvurusunu reddeder
@admin_bp.route('/borrowed/reject/<int:borrow_id>', methods=['POST'])
@admin_required
def reject_borrow(borrow_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT status FROM borrowed_books WHERE id=%s", (borrow_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'message': 'Başvuru bulunamadı'}), 404
    if row[0] != 'pending':
        cur.close()
        return jsonify({'message': 'Başvuru zaten onaylanmış veya reddedilmiş'}), 400
    cur.execute("UPDATE borrowed_books SET status='rejected' WHERE id=%s", (borrow_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Başvuru reddedildi.'})

# Kullanıcı işlemleri (admin yetkisi)

@admin_bp.route('/user/all', methods=['GET'])
@admin_required
def get_all_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT uuid, email, role FROM users")
    users = cur.fetchall()
    cur.close()

    return jsonify([{'uuid': u[0], 'email': u[1], 'role': u[2]} for u in users])

@admin_bp.route('/user/create', methods=['POST'])
@admin_bp.route('/../user/create', methods=['POST'])
def admin_create_user():
    data = request.get_json()
    email = data['email']
    password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    role = data['role']
    user_uuid = str(uuid.uuid4())

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (uuid, email, password, role) VALUES (%s, %s, %s, %s)",
                (user_uuid, email, password, role))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Kullanıcı oluşturuldu', 'uuid': user_uuid})

@admin_bp.route('/user/update/<user_uuid>', methods=['PUT'])
@admin_required
def admin_update_user(user_uuid):
    data = request.get_json()
    email = data['email']
    role = data['role']

    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET email=%s, role=%s WHERE uuid=%s", (email, role, user_uuid))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Kullanıcı güncellendi'})

@admin_bp.route('/user/delete/<user_uuid>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_uuid):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE uuid=%s", (user_uuid,))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Kullanıcı silindi'})

# Kitap işlemleri (admin yetkisi)

@admin_bp.route('/book/all', methods=['GET'])
@admin_required
def get_all_books():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, title, category, pages FROM books")
    books = cur.fetchall()
    cur.close()

    return jsonify([{'id': b[0], 'title': b[1], 'category': b[2], 'pages': b[3]} for b in books])

@admin_bp.route('/book/create', methods=['POST'])
@admin_required
def create_book():
    data = request.get_json()
    title = data['title']
    category = data['category']
    pages = data['pages']

    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO books (title, category, pages) VALUES (%s, %s, %s)", (title, category, pages))
        mysql.connection.commit()
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cur.close()

    return jsonify({'message': 'Kitap eklendi'})

@admin_bp.route('/book/update/<int:book_id>', methods=['PUT'])
@admin_required
def update_book(book_id):
    data = request.get_json()
    title = data.get('title')
    category = data.get('category')
    pages = data.get('pages')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM books WHERE id = %s", (book_id,))
    book = cur.fetchone()
    if not book:
        return jsonify({'message': 'Kitap bulunamadı'}), 404

    # Güncelleme yap
    update_query = "UPDATE books SET title=%s, category=%s, pages=%s WHERE id=%s"
    cur.execute(update_query, (title or book[1], category or book[2], pages or book[3], book_id))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Kitap güncellendi'})

@admin_bp.route('/book/delete/<int:book_id>', methods=['DELETE'])
@admin_required
def delete_book(book_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM books WHERE id = %s", (book_id,))
    book = cur.fetchone()
    if not book:
        return jsonify({'message': 'Kitap bulunamadı'}), 404

    cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Kitap silindi'})
