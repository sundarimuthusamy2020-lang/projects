"""
Flask Application for Hybrid LSB-DCT Steganography.
Provides Web UI, REST APIs, User Authentication, and History Logging.
"""

import os
import uuid
from datetime import datetime
from functools import wraps

import cv2
import numpy as np
from flask import (
    Flask, render_template, request, jsonify, redirect,
    url_for, session, flash, send_from_directory, abort
)
from werkzeug.utils import secure_filename

from models import db, User, OperationHistory
from stego import (
    embed_lsb_dct, extract_lsb_dct, calculate_capacity, calculate_psnr
)

# Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lsb-dct-stego-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'steganography.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database
db.init_app(app)
with app.app_context():
    db.create_all()


def allowed_file(filename: str) -> bool:
    """Check if uploaded file has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user():
    """Retrieve logged-in user from session if present."""
    user_id = session.get('user_id')
    if user_id:
        return db.session.get(User, user_id)
    return None


def get_or_create_session_id():
    """Generate or retrieve a unique guest session ID."""
    if 'guest_session_id' not in session:
        session['guest_session_id'] = uuid.uuid4().hex
    return session['guest_session_id']


@app.context_processor
def inject_user():
    """Make current_user available to all Jinja templates."""
    return {'current_user': get_current_user()}


# ---------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('register.html')

        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username is already taken. Please choose another.', 'warning')
            return render_template('register.html')

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Migrate any guest history to the new user account
        guest_sess_id = session.get('guest_session_id')
        if guest_sess_id:
            OperationHistory.query.filter_by(session_id=guest_sess_id, user_id=None).update({'user_id': user.id})
            db.session.commit()

        session['user_id'] = user.id
        flash(f'Account created successfully! Welcome, {user.username}.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')

        session['user_id'] = user.id

        # Migrate guest history to logged in user if any
        guest_sess_id = session.get('guest_session_id')
        if guest_sess_id:
            OperationHistory.query.filter_by(session_id=guest_sess_id, user_id=None).update({'user_id': user.id})
            db.session.commit()

        flash(f'Welcome back, {user.username}!', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ---------------------------------------------------------
# Core Application Routes
# ---------------------------------------------------------

@app.route('/')
def index():
    """Main Steganography Dashboard (Encode & Decode)."""
    get_or_create_session_id()
    return render_template('index.html')


@app.route('/api/capacity', methods=['POST'])
def check_image_capacity():
    """Check max character capacity of an uploaded image."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if not file or file.filename == '':
        return jsonify({'error': 'No selected image file'}), 400

    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        if img is None:
            return jsonify({'error': 'Invalid image file format'}), 400

        h, w = img.shape[:2]
        capacity = calculate_capacity(h, w)
        return jsonify({
            'success': True,
            'width': w,
            'height': h,
            'capacity': capacity,
            'message': f"Image ({w}x{h}) can hide up to {capacity} characters."
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/encode', methods=['POST'])
def api_encode():
    """Embed secret message into cover image using Hybrid LSB-DCT."""
    user = get_current_user()
    sess_id = get_or_create_session_id()

    if 'image' not in request.files:
        return jsonify({'error': 'Please select an image file to upload.'}), 400

    file = request.files['image']
    message = request.form.get('message', '').strip()

    if not file or file.filename == '':
        return jsonify({'error': 'No image file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file format. Please upload PNG, JPG, JPEG, BMP, or WEBP.'}), 400

    if not message:
        return jsonify({'error': 'Please enter a message to hide.'}), 400

    try:
        # Read image
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

        if img is None:
            return jsonify({'error': 'Failed to decode image. Please upload a valid image file.'}), 400

        # Handle color conversion
        is_color = (len(img.shape) == 3 and img.shape[2] >= 3)
        if is_color:
            if img.shape[2] == 4:
                # RGBA -> RGB with alpha preserved
                rgb_img = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2RGB)
                alpha = img[:, :, 3]
                processed_img = np.dstack((rgb_img, alpha))
            else:
                processed_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            processed_img = img

        h, w = processed_img.shape[:2]
        capacity = calculate_capacity(h, w)
        if len(message.encode('utf-8')) > capacity:
            return jsonify({
                'error': f"Message exceeds image capacity! Max allowed: {capacity} bytes, message is {len(message.encode('utf-8'))} bytes."
            }), 400

        # Run hybrid LSB-DCT embedding
        stego_img, psnr_val = embed_lsb_dct(processed_img, message, block_size=8, quant_factor=20)

        # Save files
        file_uid = uuid.uuid4().hex
        orig_clean_name = secure_filename(file.filename) or 'cover_image'
        cover_filename = f"cover_{file_uid}.png"
        stego_filename = f"stego_{file_uid}.png"

        cover_path = os.path.join(app.config['UPLOAD_FOLDER'], cover_filename)
        stego_path = os.path.join(app.config['UPLOAD_FOLDER'], stego_filename)

        # Save original as PNG for preview
        if is_color:
            if processed_img.shape[2] == 4:
                cv2.imwrite(cover_path, cv2.cvtColor(processed_img, cv2.COLOR_RGBA2BGRA))
                cv2.imwrite(stego_path, cv2.cvtColor(stego_img, cv2.COLOR_RGBA2BGRA))
            else:
                cv2.imwrite(cover_path, cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR))
                cv2.imwrite(stego_path, cv2.cvtColor(stego_img, cv2.COLOR_RGB2BGR))
        else:
            cv2.imwrite(cover_path, processed_img)
            cv2.imwrite(stego_path, stego_img)

        # Record in history
        history_entry = OperationHistory(
            user_id=user.id if user else None,
            session_id=sess_id,
            operation_type='encode',
            original_filename=orig_clean_name,
            stego_filename=stego_filename,
            message_length=len(message),
            message_preview=message[:100] + ('...' if len(message) > 100 else ''),
            psnr=psnr_val,
            image_width=w,
            image_height=h,
            status='success'
        )
        db.session.add(history_entry)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Message successfully embedded into image!',
            'psnr': psnr_val,
            'cover_image_url': url_for('static', filename=f"uploads/{cover_filename}"),
            'stego_image_url': url_for('static', filename=f"uploads/{stego_filename}"),
            'download_url': url_for('download_file', filename=stego_filename),
            'stego_filename': stego_filename,
            'dimensions': f"{w}x{h}",
            'message_length': len(message),
            'capacity': capacity
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/decode', methods=['POST'])
def api_decode():
    """Extract secret message from stego image using Hybrid LSB-DCT."""
    user = get_current_user()
    sess_id = get_or_create_session_id()

    if 'image' not in request.files:
        return jsonify({'error': 'Please select an image file to decode.'}), 400

    file = request.files['image']
    if not file or file.filename == '':
        return jsonify({'error': 'No image file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file format. Please upload PNG, JPG, JPEG, BMP, or WEBP.'}), 400

    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

        if img is None:
            return jsonify({'error': 'Failed to decode image file.'}), 400

        is_color = (len(img.shape) == 3 and img.shape[2] >= 3)
        if is_color:
            rgb_img = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2RGB)
            target_img = rgb_img
        else:
            target_img = img

        h, w = target_img.shape[:2]

        # Extract message
        extracted = extract_lsb_dct(target_img, block_size=8, quant_factor=20)
        orig_clean_name = secure_filename(file.filename) or 'stego_image'

        # Record in history
        history_entry = OperationHistory(
            user_id=user.id if user else None,
            session_id=sess_id,
            operation_type='decode',
            original_filename=orig_clean_name,
            stego_filename=None,
            message_length=len(extracted),
            message_preview=extracted[:100] + ('...' if len(extracted) > 100 else ''),
            psnr=None,
            image_width=w,
            image_height=h,
            status='success' if extracted else 'no_message_found'
        )
        db.session.add(history_entry)
        db.session.commit()

        return jsonify({
            'success': True,
            'extracted_message': extracted,
            'message_length': len(extracted),
            'dimensions': f"{w}x{h}",
            'filename': orig_clean_name
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/history')
def history():
    """User operation history page."""
    user = get_current_user()
    sess_id = get_or_create_session_id()

    if user:
        records = OperationHistory.query.filter_by(user_id=user.id).order_by(OperationHistory.created_at.desc()).all()
    else:
        records = OperationHistory.query.filter_by(session_id=sess_id, user_id=None).order_by(OperationHistory.created_at.desc()).all()

    return render_template('history.html', records=records)


@app.route('/history/delete/<int:record_id>', methods=['POST'])
def delete_history_record(record_id: int):
    """Delete a specific history entry."""
    user = get_current_user()
    sess_id = get_or_create_session_id()

    record = db.session.get(OperationHistory, record_id)
    if not record:
        flash('History record not found.', 'warning')
        return redirect(url_for('history'))

    # Verify authorization
    if (user and record.user_id == user.id) or (not user and record.session_id == sess_id and record.user_id is None):
        # Remove files if they exist
        if record.stego_filename:
            path = os.path.join(app.config['UPLOAD_FOLDER'], record.stego_filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        db.session.delete(record)
        db.session.commit()
        flash('History item deleted.', 'info')
    else:
        flash('Permission denied to delete this record.', 'danger')

    return redirect(url_for('history'))


@app.route('/history/clear', methods=['POST'])
def clear_history():
    """Clear all history for current user or session."""
    user = get_current_user()
    sess_id = get_or_create_session_id()

    if user:
        OperationHistory.query.filter_by(user_id=user.id).delete()
    else:
        OperationHistory.query.filter_by(session_id=sess_id, user_id=None).delete()

    db.session.commit()
    flash('All history records cleared.', 'info')
    return redirect(url_for('history'))


@app.route('/download/<filename>')
def download_file(filename: str):
    """Securely download generated stego image."""
    safe_name = secure_filename(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
    if not os.path.exists(file_path):
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_name, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
