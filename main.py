from flask import Flask, request, redirect, url_for, render_template, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_babel import Babel
from flask_babel import Babel, gettext as _
from flask import Flask, session, redirect, url_for, render_template, request, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from datetime import datetime



app = Flask(__name__)
babel = Babel(app)
app.config['SECRET_KEY'] = 'any-secret-key-you-choose'
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')  # Set the upload folder path

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    date_of_birth = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(10000))
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.Integer, nullable=False)
    db.UniqueConstraint('user_id', 'task_id', name='unique_user_task_like')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


admin = Admin(app)
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Task, db.session))
admin.add_view(ModelView(Like, db.session))
admin.add_view(ModelView(Comment, db.session))
@app.route('/')
def home():
    return render_template('get_started.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        date_of_birth = request.form['date_of_birth']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(phone=phone).first():
            flash('Phone number already registered')
            return redirect(url_for('register'))

        new_user = User(name=name, phone=phone, date_of_birth=date_of_birth, email=email,password=password )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']

        user = User.query.filter_by(phone=phone, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('register'))

    return render_template('login.html')


@app.route('/add_comment/<int:task_id>', methods=['GET', 'POST'])
def add_comment(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user.is_verified:
        return "You need to be verified to add comments.", 403

    if request.method == 'POST':
        content = request.form['content']
        new_comment = Comment(content=content, user_id=user_id, task_id=task_id)
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('add_comment.html', task_id=task_id)


@app.route('/task_comments/<int:task_id>')
def task_comments(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    task = Task.query.get_or_404(task_id)
    comments = Comment.query.filter_by(task_id=task_id).order_by(Comment.created_at).all()

    return render_template('task_comments.html', task=task, comments=comments)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    tasks = Task.query.all()

    # Get the task IDs the current user has liked
    liked_tasks = [like.task_id for like in Like.query.filter_by(user_id=user_id).all()]

    # Get the like counts for each task
    like_counts = {task.id: Like.query.filter_by(task_id=task.id).count() for task in tasks}

    return render_template('dashboard.html', user=user, tasks=tasks, liked_tasks=liked_tasks, like_counts=like_counts)


@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user.is_verified:
        flash('Only verified users can add tasks.')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        user_id = session['user_id']
        image = None
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                filename = secure_filename(image_file.filename)
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image = filename

        new_task = Task(title=title, description=description, image=image, user_id=user_id)
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('add_task.html')


@app.route('/complete_task/<int:task_id>')
def complete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    task = Task.query.get(task_id)
    if task:
        task.completed = not task.completed
        db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/like_task/<int:task_id>', methods=['POST'])
def like_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    like = Like.query.filter_by(user_id=user_id, task_id=task_id).first()

    if like:
        # Unlike the task if already liked
        db.session.delete(like)
    else:
        # Like the task
        new_like = Like(user_id=user_id, task_id=task_id)
        db.session.add(new_like)

    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']

        if new_username:
            user.name = new_username
        if new_password:
            user.password = generate_password_hash(new_password,
                                                   method='pbkdf2:sha256')  # Use a different hashing method

        db.session.commit()
        flash('Settings updated successfully!')
        return redirect(url_for('dashboard'))

    return render_template('settings.html', user=user)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
