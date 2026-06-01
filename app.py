from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret123'

DATABASE = 'clothes.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            full_name TEXT
        )
    ''')
    
    # Таблица товаров (одежда)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            brand TEXT,
            size TEXT,
            color TEXT,
            price REAL,
            stock INTEGER,
            category TEXT,
            material TEXT,
            season TEXT
        )
    ''')
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_date TEXT,
            status TEXT,
            total_amount REAL,
            shipping_address TEXT
        )
    ''')
    
    # Добавляем тестовых пользователей
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      ('admin', hash_password('123'), 'admin', 'Администратор'))
        cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      ('manager', hash_password('123'), 'manager', 'Менеджер'))
        cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                      ('client', hash_password('123'), 'client', 'Клиент'))
    
    # Добавляем тестовые товары (одежда)
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products = [
            ('Футболка хлопковая', 'Nike', 'S', 'Белый', 1990, 25, 'футболки', 'хлопок', 'лето'),
            ('Джинсы классические', 'Levi\'s', '32/32', 'Синий', 4990, 15, 'джинсы', 'деним', 'всесезон'),
            ('Куртка кожаная', 'Bershka', 'L', 'Черный', 12990, 5, 'куртки', 'кожа', 'осень'),
            ('Рубашка офисная', 'Henderson', '40', 'Белый', 3990, 8, 'рубашки', 'хлопок', 'весна'),
            ('Пальто зимнее', 'Mango', 'S', 'Бежевый', 15990, 3, 'пальто', 'шерсть', 'зима'),
        ]
        for p in products:
            cursor.execute("INSERT INTO products (name, brand, size, color, price, stock, category, material, season) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", p)
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                           (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_products'))
            elif user['role'] == 'manager':
                return redirect(url_for('manager_products'))
            else:
                return redirect(url_for('client_products'))
        else:
            flash('Неверный логин или пароль')
    
    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form['full_name']
        
        # Проверка на пустые поля
        if not username or not password or not full_name:
            flash('Заполните все поля')
            return redirect(url_for('register'))
        
        # Проверка совпадения паролей
        if password != confirm_password:
            flash('Пароли не совпадают')
            return redirect(url_for('register'))
        
        # Проверка длины пароля
        if len(password) < 3:
            flash('Пароль должен быть не менее 3 символов')
            return redirect(url_for('register'))
        
        conn = get_db()
        
        # Проверка, существует ли пользователь
        existing_user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
            flash('Пользователь с таким логином уже существует')
            conn.close()
            return redirect(url_for('register'))
        
        # Создаем нового пользователя с ролью 'client'
        conn.execute("INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), 'client', full_name))
        conn.commit()
        conn.close()
        
        flash('Регистрация успешна! Теперь вы можете войти')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы')
    return redirect(url_for('login'))

@app.route('/guest')
def guest_products():
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('guest_products.html', products=products)

@app.route('/client')
def client_products():
    if 'user_id' not in session or session.get('role') != 'client':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('client_products.html', products=products)

@app.route('/manager/products')
def manager_products():
    if 'user_id' not in session or session.get('role') != 'manager':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    conn = get_db()
    
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    season = request.args.get('season', '')
    sort = request.args.get('sort', '')
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR brand LIKE ?)"
        params.append(f'%{search}%')
        params.append(f'%{search}%')
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if season:
        query += " AND season = ?"
        params.append(season)
    
    if sort == 'price_asc':
        query += " ORDER BY price ASC"
    elif sort == 'price_desc':
        query += " ORDER BY price DESC"
    else:
        query += " ORDER BY name ASC"
    
    products = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    seasons = conn.execute("SELECT DISTINCT season FROM products").fetchall()
    
    conn.close()
    
    return render_template('manager_products.html', 
                         products=products, 
                         categories=categories,
                         seasons=seasons)

@app.route('/manager/orders')
def manager_orders():
    if 'user_id' not in session or session.get('role') != 'manager':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY order_date DESC").fetchall()
    conn.close()
    return render_template('manager_orders.html', orders=orders)

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('admin_products.html', products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = get_db()
        conn.execute("INSERT INTO products (name, brand, size, color, price, stock, category, material, season) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (request.form['name'], request.form['brand'], request.form['size'],
                     request.form['color'], float(request.form['price']), 
                     int(request.form['stock']), request.form['category'],
                     request.form['material'], request.form['season']))
        conn.commit()
        conn.close()
        flash('Товар добавлен')
        return redirect(url_for('admin_products'))
    
    return render_template('add_product.html')

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    conn = get_db()
    
    if request.method == 'POST':
        conn.execute("UPDATE products SET name=?, brand=?, size=?, color=?, price=?, stock=?, category=?, material=?, season=? WHERE id=?",
                    (request.form['name'], request.form['brand'], request.form['size'],
                     request.form['color'], float(request.form['price']), 
                     int(request.form['stock']), request.form['category'],
                     request.form['material'], request.form['season'], id))
        conn.commit()
        flash('Товар обновлен')
        return redirect(url_for('admin_products'))
    
    product = conn.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/admin/product/delete/<int:id>')
def delete_product(id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Нет доступа')
        return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Товар удален')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Нет доступа')
        return redirect(url_for('login'))
    return render_template('admin_orders.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)