"""
Database models for Users and Steganography Operation History.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    histories = db.relationship(
        'OperationHistory',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class OperationHistory(db.Model):
    __tablename__ = 'operation_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    session_id = db.Column(db.String(64), nullable=True, index=True)
    
    # 'encode' or 'decode'
    operation_type = db.Column(db.String(10), nullable=False)
    
    # Filenames stored in static/uploads
    original_filename = db.Column(db.String(255), nullable=False)
    stego_filename = db.Column(db.String(255), nullable=True)
    
    # Metrics and details
    message_length = db.Column(db.Integer, default=0)
    message_preview = db.Column(db.Text, nullable=True)
    psnr = db.Column(db.Float, nullable=True)
    image_width = db.Column(db.Integer, nullable=True)
    image_height = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='success')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'operation_type': self.operation_type,
            'original_filename': self.original_filename,
            'stego_filename': self.stego_filename,
            'message_length': self.message_length,
            'message_preview': self.message_preview,
            'psnr': self.psnr,
            'image_dimensions': f"{self.image_width}x{self.image_height}" if self.image_width and self.image_height else "N/A",
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self) -> str:
        return f"<OperationHistory id={self.id} type={self.operation_type} user_id={self.user_id}>"
