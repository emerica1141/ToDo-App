from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from sqlalchemy.orm import relationship
from datetime import date
from db import db
from config import SECRET_KEY

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///to-do-db.db"

db.init_app(app)


# Login manager

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# User Database

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    todos = relationship("ToDo", back_populates="author")

    # relationship for Archive's table
    archives = relationship("Archive", back_populates="author")

# Task Database

class ToDo(db.Model):
    __tablename__ = "todos"
    id = db.Column(db.Integer, primary_key=True)
    task_title = db.Column(db.String(50), nullable=False) 
    task_description = db.Column(db.String(100), nullable=False) 
    priority = db.Column(db.Integer, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="todos")
    created_at = db.Column(db.String(100))

    # relationship with Arhieve db model
    # first_created = relationship("Archive", back_populates="created")

# Archive Database - Here will go tasks that have been "Marked as Done"

class Archive(db.Model):
    __tablename__ = "archive"
    id = db.Column(db.Integer, primary_key=True)
    task_title = db.Column(db.String(50), nullable=False) 
    task_description = db.Column(db.String(100), nullable=False) 
    priority = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(100))
    finished_at = db.Column(db.String(100))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # relationship with User's table
    author = relationship("User", back_populates="archives")

with app.app_context():
    db.create_all()


# ---------------------- INDEX ROUTE ----------------------
@app.route("/")
def home():

    tasks_list = db.session.execute(db.select(ToDo).order_by(ToDo.priority))
    all_tasks = tasks_list.scalars()

    return render_template("index.html", tasks=all_tasks)

# ---------------------- ARCHIVE ROUTE ----------------------

@app.route("/archive")
@login_required
def archive():

    archive_list = db.session.execute(db.select(Archive).order_by(Archive.finished_at))
    full_archive = archive_list.scalars()

    return render_template("archive.html", archive=full_archive)

# ---------------------- DELETE ARCHIVE TASK ROUTE ----------------------

@app.route("/archive/delete")
@login_required
def archive_item_delete():

    task_id = request.args.get('id')
    task_to_delete = db.session.execute(db.select(Archive).where(Archive.id == task_id)).scalar()
    db.session.delete(task_to_delete)
    db.session.commit()

    return redirect(url_for('archive'))

@app.route("/archive/undo")
@login_required

def archive_item_undo():

    task_id = request.args.get('id')
    task_to_undo = db.session.execute(db.select(Archive).where(Archive.id == task_id)).scalar()

    undo_task = ToDo(task_title=task_to_undo.task_title, 
                task_description=task_to_undo.task_description, 
                priority=task_to_undo.priority,
                author_id=task_to_undo.author_id,
                created_at=task_to_undo.created_at)
    
    db.session.add(undo_task)
    db.session.delete(task_to_undo)
    db.session.commit()

    return redirect(url_for('home'))


# ---------------------- ADD TASK ROUTE ----------------------

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_task():


    if request.method == "POST":

        new_task = ToDo(
            task_title=request.form["task"], 
            task_description=request.form["description"], 
            priority=request.form["priority"],
            author_id=current_user.id,
            created_at=date.today())

        
        db.session.add(new_task)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template("add.html")

# ---------------------- EDIT TASK ROUTE ----------------------

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    task_id = request.args.get('id')
    task_to_edit = db.session.execute(db.select(ToDo).where(ToDo.id == task_id)).scalar()

    if request.method == "POST":
        task_to_edit = db.session.execute(db.select(ToDo).where(ToDo.id == task_id)).scalar()
        task_to_edit.task_title = request.form["edit_task"]
        task_to_edit.task_description = request.form["edit_description"]
        task_to_edit.priority = request.form["edit_priority"]
        db.session.commit()

        return redirect(url_for('home'))
    
    return render_template("edit.html", editable=task_to_edit)

# ---------------------- DELETE TASK ROUTE ----------------------

@app.route("/delete")
@login_required
def delete():
    task_id = request.args.get('id')
    task_to_delete = db.session.execute(db.select(ToDo).where(ToDo.id == task_id)).scalar()
    db.session.delete(task_to_delete)
    db.session.commit()

    return redirect(url_for('home'))

@app.route("/about")
def about():
    
    return render_template("about.html")


# ---------------------- REGISTER ROUTE ----------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # Check if entered passwords match
        if request.form['password'] == request.form['password_confirm']:
            hash_password = generate_password_hash(
                request.form["password"],
                method='pbkdf2:sha256',
                salt_length=8
            )
        
        # Add user to database

        new_user = User(
            username = request.form["username"],
            email = request.form["email"],
            password = hash_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('successful_reg'))

    return render_template("register.html")

# ---------------------- SUCCESSFUL REGISTRATION ROUTE ----------------------

@app.route("/success")
def successful_reg():

    return render_template("successreg.html")

# ---------------------- ROUTE TO MOVE TASKS THAT HAVE BEEN DONE FROM ToDo TABLE TO ARCHIVE TABLE ----------------------

@app.route("/task_done")
@login_required
def task_done():

    # Get task id
    task_id = request.args.get('id')
    # Get task data as list
    task_done = db.session.execute(db.Select(ToDo).where(ToDo.id == task_id)).scalar()

    # Add row to Archive table 
    task_to_archive = Archive(
        task_title=task_done.task_title,
        task_description=task_done.task_description,
        priority=task_done.priority,
        created_at=task_done.created_at,
        finished_at=date.today(),
        author_id=task_done.author_id,
    )

    # Add task_to_archive to Archive table
    db.session.add(task_to_archive)
    # Delete same task from ToDo table
    db.session.delete(task_done)
    db.session.commit()

    return redirect(url_for('home'))

# ---------------------- LOGIN ROUTE ----------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        result = db.session.execute(db.select(User).where(User.username == username))
        user = result.scalar()
        
        if not user:
            flash("Please enter correct username or password")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash("Please enter correct username or password")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))

    return render_template("login.html")

# ---------------------- LOGOUT ROUTE ----------------------

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()

    return redirect(url_for('home'))


# ---------------------- USER PROFILE ROUTE ----------------------

@app.route("/profile/user_data")
@login_required
def user_data():

    return render_template("/user_profile/user_data.html")


# ---------------------- USER CHANGE PASSWORD ROUTE ----------------------

@app.route("/profile/password", methods = ["GET", "POST"])
@login_required
def edit_password():

    if request.method == "POST":

        password = current_user.password
        current_password = request.form['old_password']

        if check_password_hash(password, current_password):

            if request.form['password'] == request.form['password_confirm']:
                hash_password = generate_password_hash(
                request.form["password"],
                method='pbkdf2:sha256',
                salt_length=8
            )
                
                user = db.session.execute(db.select(User).where(User.username == current_user.username)).scalar()
                user.password = hash_password
                db.session.commit()
                
            else:
                flash("New passwords does not match")
        else:
            flash("Please enter correct current password")


    return render_template("/user_profile/edit_password.html")


# ---------------------- USER CHANGE EMAIL ROUTE ----------------------

@app.route("/profile/email", methods=["GET", "POST"])
@login_required
def edit_email():

    if request.method == "POST":
    
        if request.form['email'] == request.form['email_confirm']:
            new_email = request.form['email']
            user = db.session.execute(db.select(User).where(User.username == current_user.username)).scalar()

            user.email = new_email
            db.session.commit()

        else:
            flash("New emails does not match")

        return redirect(url_for('edit_email'))

    return render_template("/user_profile/edit_email.html")




if __name__ == "__main__":
    app.run(debug=True)



