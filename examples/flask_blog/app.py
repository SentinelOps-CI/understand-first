"""
Flask Blog Application Example
=============================

This example demonstrates Understand-First with a Flask blog application.
It shows how the tool handles Flask patterns, blueprints, authentication,
and complex business logic.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import (
    StringField,
    TextAreaField,
    PasswordField,
    BooleanField,
    SelectField,
    HiddenField,
)
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
import json
from typing import List, Dict, Optional, Any
from functools import wraps
import redis
from celery import Celery
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_ENABLED"] = True

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
csrf = CSRFProtect(app)

# Initialize Redis for caching
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)

# Initialize Celery for background tasks
celery = Celery(
    app.name,
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)


# Database Models
class User(UserMixin, db.Model):
    """User model for authentication and profile management."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    posts = db.relationship("Post", backref="author", lazy="dynamic", cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", backref="author", lazy="dynamic", cascade="all, delete-orphan"
    )
    likes = db.relationship("Like", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """Set password hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)

    def get_full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"

    def get_posts_count(self) -> int:
        """Get total number of posts by user."""
        return self.posts.count()

    def get_likes_count(self) -> int:
        """Get total number of likes received."""
        return db.session.query(Like).join(Post).filter(Post.author_id == self.id).count()

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
            "posts_count": self.get_posts_count(),
            "likes_count": self.get_likes_count(),
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Category(db.Model):
    """Category model for organizing posts."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), default="#667eea", nullable=False)  # Hex color
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    posts = db.relationship("Post", backref="category", lazy="dynamic")

    def get_posts_count(self) -> int:
        """Get number of posts in this category."""
        return self.posts.count()

    def to_dict(self) -> Dict[str, Any]:
        """Convert category to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "color": self.color,
            "posts_count": self.get_posts_count(),
        }

    def __repr__(self) -> str:
        return f"<Category {self.name}>"


class Post(db.Model):
    """Post model for blog articles."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text, nullable=True)
    featured_image = db.Column(db.String(200), nullable=True)
    status = db.Column(
        db.String(20), default="draft", nullable=False, index=True
    )  # draft, published, archived
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    allow_comments = db.Column(db.Boolean, default=True, nullable=False)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)

    # Foreign keys
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)

    # Relationships
    comments = db.relationship(
        "Comment", backref="post", lazy="dynamic", cascade="all, delete-orphan"
    )
    likes = db.relationship("Like", backref="post", lazy="dynamic", cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary="post_tag", backref="posts", lazy="dynamic")

    def get_excerpt(self, length: int = 150) -> str:
        """Get post excerpt."""
        if self.excerpt:
            return self.excerpt
        return self.content[:length] + "..." if len(self.content) > length else self.content

    def get_likes_count(self) -> int:
        """Get number of likes for this post."""
        return self.likes.count()

    def get_comments_count(self) -> int:
        """Get number of comments for this post."""
        return self.comments.count()

    def increment_view_count(self) -> None:
        """Increment view count."""
        self.view_count += 1
        db.session.commit()

    def is_published(self) -> bool:
        """Check if post is published."""
        return self.status == "published" and self.published_at is not None

    def can_be_edited_by(self, user: User) -> bool:
        """Check if user can edit this post."""
        return user.is_admin or user.id == self.author_id

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        """Convert post to dictionary."""
        data = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "excerpt": self.get_excerpt(),
            "featured_image": self.featured_image,
            "status": self.status,
            "is_featured": self.is_featured,
            "allow_comments": self.allow_comments,
            "view_count": self.view_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "author": self.author.to_dict(),
            "category": self.category.to_dict() if self.category else None,
            "likes_count": self.get_likes_count(),
            "comments_count": self.get_comments_count(),
            "tags": [tag.to_dict() for tag in self.tags],
        }

        if include_content:
            data["content"] = self.content

        return data

    def __repr__(self) -> str:
        return f"<Post {self.title}>"


class Comment(db.Model):
    """Comment model for post comments."""

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign keys
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("comment.id"), nullable=True)

    # Relationships
    replies = db.relationship(
        "Comment", backref=db.backref("parent", remote_side=[id]), lazy="dynamic"
    )

    def get_replies_count(self) -> int:
        """Get number of replies to this comment."""
        return self.replies.count()

    def to_dict(self) -> Dict[str, Any]:
        """Convert comment to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "is_approved": self.is_approved,
            "created_at": self.created_at.isoformat(),
            "author": self.author.to_dict(),
            "replies_count": self.get_replies_count(),
            "replies": [reply.to_dict() for reply in self.replies.filter_by(is_approved=True)],
        }

    def __repr__(self) -> str:
        return f"<Comment {self.id}>"


class Tag(db.Model):
    """Tag model for post tagging."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    color = db.Column(db.String(7), default="#6c757d", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def get_posts_count(self) -> int:
        """Get number of posts with this tag."""
        return self.posts.count()

    def to_dict(self) -> Dict[str, Any]:
        """Convert tag to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "color": self.color,
            "posts_count": self.get_posts_count(),
        }

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class Like(db.Model):
    """Like model for post likes."""

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)

    # Unique constraint
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="unique_user_post_like"),)

    def __repr__(self) -> str:
        return f"<Like {self.user_id} -> {self.post_id}>"


# Association table for many-to-many relationship
post_tag = db.Table(
    "post_tag",
    db.Column("post_id", db.Integer, db.ForeignKey("post.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


# Forms
class LoginForm(FlaskForm):
    """Login form."""

    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")


class RegisterForm(FlaskForm):
    """Registration form."""

    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    first_name = StringField("First Name", validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(min=1, max=50)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])


class PostForm(FlaskForm):
    """Post creation/editing form."""

    title = StringField("Title", validators=[DataRequired(), Length(min=1, max=200)])
    content = TextAreaField("Content", validators=[DataRequired()])
    excerpt = TextAreaField("Excerpt", validators=[Optional(), Length(max=500)])
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    tags = StringField("Tags (comma-separated)", validators=[Optional()])
    featured_image = StringField("Featured Image URL", validators=[Optional()])
    status = SelectField(
        "Status", choices=[("draft", "Draft"), ("published", "Published")], default="draft"
    )
    is_featured = BooleanField("Featured Post")
    allow_comments = BooleanField("Allow Comments", default=True)


class CommentForm(FlaskForm):
    """Comment form."""

    content = TextAreaField("Comment", validators=[DataRequired(), Length(min=1, max=1000)])
    post_id = HiddenField("Post ID")


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Decorators
def admin_required(f):
    """Decorator to require admin privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def cache_result(timeout=300):
    """Decorator to cache function results."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f"{f.__name__}:{hash(str(args) + str(kwargs))}"
            cached_result = redis_client.get(cache_key)

            if cached_result:
                return json.loads(cached_result)

            result = f(*args, **kwargs)
            redis_client.setex(cache_key, timeout, json.dumps(result, default=str))
            return result

        return decorated_function

    return decorator


# Background tasks
@celery.task
def send_email_notification(recipient_email: str, subject: str, content: str):
    """Send email notification (background task)."""
    try:
        msg = MIMEMultipart()
        msg["From"] = os.environ.get("SMTP_FROM", "noreply@blog.com")
        msg["To"] = recipient_email
        msg["Subject"] = subject

        msg.attach(MIMEText(content, "html"))

        server = smtplib.SMTP(
            os.environ.get("SMTP_HOST", "localhost"), int(os.environ.get("SMTP_PORT", 587))
        )
        server.starttls()
        server.login(os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASSWORD", ""))
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")


@celery.task
def update_post_stats(post_id: int):
    """Update post statistics (background task)."""
    try:
        post = Post.query.get(post_id)
        if post:
            # Update view count in cache
            cache_key = f"post_views:{post_id}"
            redis_client.incr(cache_key)

            # Update trending posts
            trending_key = "trending_posts"
            redis_client.zincrby(trending_key, 1, post_id)

            logger.info(f"Updated stats for post {post_id}")
    except Exception as e:
        logger.error(f"Failed to update post stats: {e}")


# Business logic services
class PostService:
    """Service for post-related operations."""

    @staticmethod
    def create_post(form_data: Dict[str, Any], author: User) -> Post:
        """Create a new post."""
        post = Post(
            title=form_data["title"],
            slug=PostService._generate_slug(form_data["title"]),
            content=form_data["content"],
            excerpt=form_data.get("excerpt", ""),
            featured_image=form_data.get("featured_image", ""),
            status=form_data.get("status", "draft"),
            is_featured=form_data.get("is_featured", False),
            allow_comments=form_data.get("allow_comments", True),
            author_id=author.id,
            category_id=form_data.get("category_id"),
        )

        if post.status == "published":
            post.published_at = datetime.utcnow()

        db.session.add(post)
        db.session.flush()  # Get the ID

        # Handle tags
        if form_data.get("tags"):
            PostService._add_tags_to_post(post, form_data["tags"])

        db.session.commit()

        # Send notification
        send_email_notification.delay(
            author.email, "Post Created", f"Your post '{post.title}' has been created successfully."
        )

        logger.info(f"Created post '{post.title}' by {author.username}")
        return post

    @staticmethod
    def update_post(post: Post, form_data: Dict[str, Any]) -> Post:
        """Update an existing post."""
        post.title = form_data["title"]
        post.content = form_data["content"]
        post.excerpt = form_data.get("excerpt", "")
        post.featured_image = form_data.get("featured_image", "")
        post.status = form_data.get("status", post.status)
        post.is_featured = form_data.get("is_featured", post.is_featured)
        post.allow_comments = form_data.get("allow_comments", post.allow_comments)
        post.category_id = form_data.get("category_id")
        post.updated_at = datetime.utcnow()

        if post.status == "published" and not post.published_at:
            post.published_at = datetime.utcnow()

        # Update tags
        if form_data.get("tags"):
            post.tags.clear()
            PostService._add_tags_to_post(post, form_data["tags"])

        db.session.commit()

        logger.info(f"Updated post '{post.title}'")
        return post

    @staticmethod
    def delete_post(post: Post) -> bool:
        """Delete a post."""
        try:
            db.session.delete(post)
            db.session.commit()
            logger.info(f"Deleted post '{post.title}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete post: {e}")
            return False

    @staticmethod
    def get_published_posts(
        page: int = 1, per_page: int = 10, category_id: Optional[int] = None
    ) -> List[Post]:
        """Get published posts with pagination."""
        query = Post.query.filter_by(status="published")

        if category_id:
            query = query.filter_by(category_id=category_id)

        return query.order_by(Post.published_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def get_featured_posts(limit: int = 5) -> List[Post]:
        """Get featured posts."""
        return (
            Post.query.filter_by(status="published", is_featured=True)
            .order_by(Post.published_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_trending_posts(limit: int = 10) -> List[Post]:
        """Get trending posts based on views."""
        # Get trending post IDs from Redis
        trending_ids = redis_client.zrevrange("trending_posts", 0, limit - 1)

        if not trending_ids:
            # Fallback to database
            return (
                Post.query.filter_by(status="published")
                .order_by(Post.view_count.desc())
                .limit(limit)
                .all()
            )

        # Get posts by IDs
        posts = Post.query.filter(Post.id.in_([int(id) for id in trending_ids])).all()

        # Sort by trending order
        return sorted(posts, key=lambda p: trending_ids.index(str(p.id)))

    @staticmethod
    def search_posts(query: str, page: int = 1, per_page: int = 10) -> List[Post]:
        """Search posts by title and content."""
        search_query = f"%{query}%"
        return (
            Post.query.filter(
                Post.status == "published",
                db.or_(
                    Post.title.ilike(search_query),
                    Post.content.ilike(search_query),
                    Post.excerpt.ilike(search_query),
                ),
            )
            .order_by(Post.published_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    @staticmethod
    def _generate_slug(title: str) -> str:
        """Generate URL slug from title."""
        import re

        slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")

    @staticmethod
    def _add_tags_to_post(post: Post, tags_string: str) -> None:
        """Add tags to post."""
        tag_names = [tag.strip() for tag in tags_string.split(",") if tag.strip()]

        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name, slug=PostService._generate_slug(tag_name))
                db.session.add(tag)
                db.session.flush()

            post.tags.append(tag)


class CommentService:
    """Service for comment-related operations."""

    @staticmethod
    def create_comment(
        post_id: int, content: str, author: User, parent_id: Optional[int] = None
    ) -> Comment:
        """Create a new comment."""
        comment = Comment(
            content=content, author_id=author.id, post_id=post_id, parent_id=parent_id
        )

        db.session.add(comment)
        db.session.commit()

        # Send notification to post author
        post = Post.query.get(post_id)
        if post and post.author_id != author.id:
            send_email_notification.delay(
                post.author.email, "New Comment", f"Someone commented on your post '{post.title}'"
            )

        logger.info(f"Created comment by {author.username} on post {post_id}")
        return comment

    @staticmethod
    def get_post_comments(post_id: int, parent_id: Optional[int] = None) -> List[Comment]:
        """Get comments for a post."""
        query = Comment.query.filter_by(post_id=post_id, is_approved=True)

        if parent_id is None:
            query = query.filter_by(parent_id=None)
        else:
            query = query.filter_by(parent_id=parent_id)

        return query.order_by(Comment.created_at.asc()).all()

    @staticmethod
    def approve_comment(comment_id: int) -> bool:
        """Approve a comment."""
        try:
            comment = Comment.query.get(comment_id)
            if comment:
                comment.is_approved = True
                db.session.commit()
                logger.info(f"Approved comment {comment_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to approve comment: {e}")
            return False


# Routes
@app.route("/")
@cache_result(timeout=300)
def index():
    """Home page with featured and recent posts."""
    featured_posts = PostService.get_featured_posts(3)
    recent_posts = (
        Post.query.filter_by(status="published").order_by(Post.published_at.desc()).limit(6).all()
    )

    return render_template("index.html", featured_posts=featured_posts, recent_posts=recent_posts)


@app.route("/posts")
def posts():
    """Posts listing page."""
    page = request.args.get("page", 1, type=int)
    category_id = request.args.get("category", type=int)
    search_query = request.args.get("q", "")

    if search_query:
        posts_data = PostService.search_posts(search_query, page)
    else:
        posts_data = PostService.get_published_posts(page, category_id=category_id)

    categories = Category.query.all()

    return render_template(
        "posts.html", posts=posts_data, categories=categories, search_query=search_query
    )


@app.route("/posts/<slug>")
def post_detail(slug):
    """Post detail page."""
    post = Post.query.filter_by(slug=slug, status="published").first_or_404()

    # Increment view count
    post.increment_view_count()
    update_post_stats.delay(post.id)

    # Get comments
    comments = CommentService.get_post_comments(post.id)

    # Get related posts
    related_posts = (
        Post.query.filter(
            Post.category_id == post.category_id, Post.id != post.id, Post.status == "published"
        )
        .limit(3)
        .all()
    )

    return render_template(
        "post_detail.html", post=post, comments=comments, related_posts=related_posts
    )


@app.route("/api/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    """Like/unlike a post."""
    post = Post.query.get_or_404(post_id)

    # Check if user already liked this post
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if existing_like:
        # Unlike
        db.session.delete(existing_like)
        liked = False
    else:
        # Like
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        liked = True

    db.session.commit()

    return jsonify({"liked": liked, "likes_count": post.get_likes_count()})


@app.route("/api/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def add_comment(post_id):
    """Add a comment to a post."""
    form = CommentForm()
    if form.validate_on_submit():
        comment = CommentService.create_comment(
            post_id=post_id, content=form.content.data, author=current_user
        )

        return jsonify({"success": True, "comment": comment.to_dict()})

    return jsonify({"success": False, "errors": form.errors}), 400


# Authentication routes
@app.route("/auth/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.utcnow()
            db.session.commit()

            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("index"))

        flash("Invalid username or password", "error")

    return render_template("auth/login.html", form=form)


@app.route("/auth/register", methods=["GET", "POST"])
def register():
    """Registration page."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("auth/register.html", form=form)


@app.route("/auth/logout")
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# Admin routes
@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard."""
    stats = {
        "total_posts": Post.query.count(),
        "published_posts": Post.query.filter_by(status="published").count(),
        "total_users": User.query.count(),
        "total_comments": Comment.query.count(),
    }

    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_posts=recent_posts,
        recent_comments=recent_comments,
    )


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("errors/500.html"), 500


# Context processors
@app.context_processor
def inject_categories():
    """Inject categories into all templates."""
    categories = Category.query.all()
    return dict(categories=categories)


@app.context_processor
def inject_user_stats():
    """Inject user stats into templates."""
    if current_user.is_authenticated:
        return dict(
            user_posts_count=current_user.get_posts_count(),
            user_likes_count=current_user.get_likes_count(),
        )
    return dict()


# CLI commands
@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()

    # Create default categories
    categories = [
        {
            "name": "Technology",
            "slug": "technology",
            "description": "Tech news and tutorials",
            "color": "#667eea",
        },
        {
            "name": "Programming",
            "slug": "programming",
            "description": "Programming articles",
            "color": "#28a745",
        },
        {
            "name": "Web Development",
            "slug": "web-development",
            "description": "Web dev tutorials",
            "color": "#17a2b8",
        },
        {
            "name": "Data Science",
            "slug": "data-science",
            "description": "Data science articles",
            "color": "#ffc107",
        },
        {
            "name": "DevOps",
            "slug": "devops",
            "description": "DevOps and deployment",
            "color": "#dc3545",
        },
    ]

    for cat_data in categories:
        if not Category.query.filter_by(slug=cat_data["slug"]).first():
            category = Category(**cat_data)
            db.session.add(category)

    # Create admin user
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@blog.com",
            first_name="Admin",
            last_name="User",
            is_admin=True,
        )
        admin.set_password("admin123")
        db.session.add(admin)

    db.session.commit()
    print("Database initialized successfully!")


if __name__ == "__main__":
    app.run(debug=True)
