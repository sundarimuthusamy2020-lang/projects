# StegoCrypt: Hybrid LSB-DCT Image Steganography Web Application

A full-stack web application implementing **Hybrid Discrete Cosine Transform (DCT) and Least Significant Bit (LSB)** steganography. It allows users to secretly embed encrypted messages into cover images and extract concealed messages from stego images, while tracking a complete history of operations per user.

---

## 🚀 Key Features

1. **Encode (Hide Message into Image)**
   - Upload any cover image (PNG, JPG, JPEG, BMP, WEBP).
   - Real-time capacity calculator (calculates the maximum characters the image can hold based on 8x8 DCT blocks).
   - Capacity meter with visual progress bar and character counter.
   - Embeds message bits into the mid-frequency `(4, 3)` DCT coefficient of the Luminance ($Y$) channel.
   - Calculates **PSNR (Peak Signal-to-Noise Ratio)** in decibels (typically $> 40\text{ dB}$, ensuring high visual quality).
   - Side-by-side comparison between Original and Stego images.
   - Download the generated stego image in lossless PNG format.
   - 1-click **"Send to Decode"** shortcut for instant verification.

2. **Decode (Extract Message from Image)**
   - Upload any encrypted stego image.
   - Automatically parses DCT blocks and reconstructs the hidden binary payload.
   - UTF-8 decoding support for symbols, punctuation, and Unicode text.
   - Instant "Copy to Clipboard" with feedback.

3. **User Authentication & Per-User Operation History**
   - User Registration & Login with secure password hashing (`Werkzeug`).
   - Guest mode supported (tracks session operations until account creation/login).
   - Complete history table with operation type (`Encode` / `Decode`), date & time, image name, dimensions, PSNR value, and message preview.
   - Direct download links for past stego images and options to delete individual records or clear history.

---

## 🧠 How the Hybrid LSB-DCT Algorithm Works

1. **Color Conversion**: The input RGB image is converted into the **$\text{YCbCr}$** color space. Steganography is performed on the **Luminance ($Y$) channel**, where human vision is least sensitive to subtle frequency modifications.
2. **8x8 Block Partitioning**: The $Y$ channel is divided into non-overlapping $8 \times 8$ pixel blocks.
3. **2D Discrete Cosine Transform (DCT)**: Each spatial block is transformed into the frequency domain using `cv2.dct()`.
4. **Quantized LSB Embedding**:
   - The mid-frequency coefficient at index $(4, 3)$ is quantized with a step factor $Q = 20$:
     $$\text{quant} = \text{round}\left(\frac{\text{coef}}{Q}\right)$$
   - The secret bit is embedded into the Least Significant Bit (LSB) of this quantized value:
     $$\text{quant}_{\text{stego}} = (\text{quant} \ \& \ \sim 1) \ | \ \text{bit}$$
   - The modified coefficient is scaled back:
     $$\text{coef}_{\text{stego}} = \text{quant}_{\text{stego}} \times Q$$
5. **Inverse DCT (IDCT)**: `cv2.idct()` maps the frequency coefficients back to spatial pixels.
6. **PSNR Evaluation**:
   $$\text{MSE} = \frac{1}{M \times N} \sum (I_{\text{orig}} - I_{\text{stego}})^2$$
   $$\text{PSNR} = 20 \log_{10}\left(\frac{255}{\sqrt{\text{MSE}}}\right)$$

---

## 📁 Project Structure

```
lsb and dct stenography/
│── app.py                  # Main Flask application and REST routes
│── stego.py                # Core Hybrid LSB-DCT steganography engine
│── models.py               # SQLAlchemy database models (User & OperationHistory)
│── requirements.txt        # Python package dependencies
│── README.md               # Documentation and execution guide
│── static/
│   ├── css/
│   │   └── style.css       # Responsive dark-theme stylesheet
│   ├── js/
│   │   └── main.js         # Frontend controller (drag-drop, AJAX, capacity meter)
│   └── uploads/            # Storage folder for uploaded and generated images
└── templates/
    ├── base.html           # Base layout with navigation and alerts
    ├── index.html          # Interactive Dashboard (Encode & Decode tabs)
    ├── history.html        # User operation history table
    ├── login.html          # Sign In page
    └── register.html       # Sign Up page
```

---

## 🛠️ Installation & Setup

### 1. Requirements
Ensure Python 3.10+ is installed on your machine.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python app.py
```

### 4. Access the Website
Open your browser and navigate to:
```
http://127.0.0.1:5000
```
