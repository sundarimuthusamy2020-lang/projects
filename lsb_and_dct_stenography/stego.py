"""
Hybrid LSB-DCT Steganography Module.
Implements Discrete Cosine Transform (DCT) combined with Least Significant Bit (LSB)
substitution on mid-frequency coefficients with quantization factor for robust embedding
and lossless recovery.
"""

import cv2
import numpy as np


def rgb2ycbcr(im: np.ndarray) -> np.ndarray:
    """Convert RGB image to YCbCr color space."""
    xform = np.array([[0.299, 0.587, 0.114],
                      [-0.1687, -0.3313, 0.5],
                      [0.5, -0.4187, -0.0813]], dtype=np.float64)
    ycbcr = im.astype(np.float64).dot(xform.T)
    ycbcr[:, :, [1, 2]] += 128.0
    return np.clip(ycbcr, 0, 255).astype(np.uint8)


def ycbcr2rgb(im: np.ndarray) -> np.ndarray:
    """Convert YCbCr image back to RGB color space."""
    xform = np.array([[1.0, 0.0, 1.402],
                      [1.0, -0.34414, -0.71414],
                      [1.0, 1.772, 0.0]], dtype=np.float64)
    rgb = im.astype(np.float64)
    rgb[:, :, [1, 2]] -= 128.0
    rgb = rgb.dot(xform.T)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def string_to_binary(message: str) -> str:
    """Convert string to binary using UTF-8 encoding."""
    raw_bytes = message.encode('utf-8')
    return ''.join(format(b, '08b') for b in raw_bytes)


def binary_to_string(binary: str) -> str:
    """Convert binary bits back to UTF-8 string."""
    byte_list = bytearray()
    for i in range(0, len(binary), 8):
        byte_str = binary[i:i + 8]
        if len(byte_str) == 8:
            byte_list.append(int(byte_str, 2))
    return byte_list.decode('utf-8', errors='replace')


def calculate_capacity(height: int, width: int, block_size: int = 8) -> int:
    """
    Calculate maximum character capacity that can be stored in the image.
    Each 8x8 block carries 1 bit. 8 bits = 1 byte (character).
    We reserve 1 byte (8 bits) for the null terminator.
    """
    total_blocks = (height // block_size) * (width // block_size)
    max_bytes = max(0, (total_blocks - 8) // 8)
    return max_bytes


def calculate_psnr(original: np.ndarray, modified: np.ndarray) -> float:
    """Calculate Peak Signal-to-Noise Ratio (PSNR) between original and stego image."""
    mse = np.mean((original.astype(np.float64) - modified.astype(np.float64)) ** 2)
    if mse == 0:
        return float('inf')
    max_pixel = 255.0
    psnr = 20.0 * np.log10(max_pixel / np.sqrt(mse))
    return float(round(psnr, 2))


def embed_lsb_dct(image: np.ndarray, message: str, block_size: int = 8, quant_factor: int = 20) -> tuple[np.ndarray, float]:
    """
    Embed message using hybrid LSB-DCT approach.
    Modifies mid-frequency coefficient (4, 3) in 8x8 DCT blocks of the Y-channel.
    Returns: (stego_image, psnr_value)
    """
    # Convert message to binary with null terminator (8 zero bits)
    binary_message = string_to_binary(message)
    binary_message += '00000000'

    is_color = (len(image.shape) == 3 and image.shape[2] >= 3)
    if is_color:
        rgb_image = image[:, :, :3]
        ycbcr = rgb2ycbcr(rgb_image)
        y_channel = ycbcr[:, :, 0].copy()
    else:
        y_channel = image.copy()

    height, width = y_channel.shape
    total_blocks = (height // block_size) * (width // block_size)
    blocks_needed = len(binary_message)

    if blocks_needed > total_blocks:
        max_chars = calculate_capacity(height, width, block_size)
        raise ValueError(
            f"Message is too long ({len(message)} chars). "
            f"Image can store at most {max_chars} characters ({total_blocks} blocks available)."
        )

    message_index = 0
    # Embed data into mid-frequency DCT coefficients
    for i in range(0, height - block_size + 1, block_size):
        for j in range(0, width - block_size + 1, block_size):
            if message_index >= len(binary_message):
                break

            block = y_channel[i:i + block_size, j:j + block_size].astype(np.float32)
            dct_block = cv2.dct(block)

            # Mid-frequency coefficient at (4, 3)
            coef = dct_block[4, 3]
            # Quantize
            coef_quant = int(np.round(coef / quant_factor))
            bit = int(binary_message[message_index])
            # Embed bit into LSB of quantized coefficient
            coef_quant = (coef_quant & ~1) | bit
            dct_block[4, 3] = float(coef_quant * quant_factor)
            message_index += 1

            # Inverse DCT
            idct_block = cv2.idct(dct_block)
            y_channel[i:i + block_size, j:j + block_size] = np.clip(np.round(idct_block), 0, 255).astype(np.uint8)

        if message_index >= len(binary_message):
            break

    # Reconstruct stego image
    if is_color:
        ycbcr[:, :, 0] = y_channel
        stego_image = ycbcr2rgb(ycbcr)
        # Preserve alpha channel if original had it
        if image.shape[2] == 4:
            stego_image = np.dstack((stego_image, image[:, :, 3]))
    else:
        stego_image = y_channel

    psnr_val = calculate_psnr(image[:, :, :3] if is_color else image,
                              stego_image[:, :, :3] if is_color else stego_image)
    return stego_image, psnr_val


def extract_lsb_dct(stego_image: np.ndarray, block_size: int = 8, quant_factor: int = 20, max_message_len: int = 20000) -> str:
    """
    Extract message from stego image using hybrid LSB-DCT approach.
    Inspects mid-frequency coefficient (4, 3) of 8x8 DCT blocks.
    """
    is_color = (len(stego_image.shape) == 3 and stego_image.shape[2] >= 3)
    if is_color:
        rgb_image = stego_image[:, :, :3]
        ycbcr = rgb2ycbcr(rgb_image)
        y_channel = ycbcr[:, :, 0]
    else:
        y_channel = stego_image

    height, width = y_channel.shape
    binary_message = ""
    max_bits = max_message_len * 8

    for i in range(0, height - block_size + 1, block_size):
        for j in range(0, width - block_size + 1, block_size):
            if len(binary_message) >= max_bits:
                break

            block = y_channel[i:i + block_size, j:j + block_size].astype(np.float32)
            dct_block = cv2.dct(block)

            coef = dct_block[4, 3]
            coef_quant = int(np.round(coef / quant_factor))
            bit = coef_quant & 1
            binary_message += str(bit)

            # Check if we reached null terminator (last byte is 00000000)
            if len(binary_message) % 8 == 0 and binary_message.endswith('00000000'):
                clean_binary = binary_message[:-8]
                return binary_to_string(clean_binary)

        if len(binary_message) >= max_bits:
            break

    # If terminator wasn't encountered, convert whatever was extracted
    return binary_to_string(binary_message)
