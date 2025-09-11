# =====================================================================
# PERBAIKAN: features/dicom_import/logic/pixel_analyzer.py
# =====================================================================

import numpy as np
from typing import Tuple, Dict
from PIL import Image
import logging
def analyze_background_type(frame_data: np.ndarray) -> Dict[str, any]:
    """Enhanced with extensive debugging"""
    logging.info(f"\n  === BACKGROUND ANALYSIS DEBUG ===")
    logging.info(f"Frame shape: {frame_data.shape}")
    logging.info(f"Frame dtype: {frame_data.dtype}")
    logging.info(f"Frame range: {frame_data.min()} to {frame_data.max()}")
    
    if frame_data is None or frame_data.size == 0:
        logging.info(" ERROR: Empty or None frame data")
        return {"background_type": "black", "confidence": 0}
    
    # Normalize to uint8 if needed
    if frame_data.dtype != np.uint8:
        frame_norm = (frame_data - frame_data.min()) / max(frame_data.max() - frame_data.min(), 1)
        frame_uint8 = (frame_norm * 255).astype(np.uint8)
        logging.info(f"🔄 Normalized to uint8: {frame_uint8.min()} to {frame_uint8.max()}")
    else:
        frame_uint8 = frame_data.copy()
        logging.info(f"  Already uint8: {frame_uint8.min()} to {frame_uint8.max()}")
    
    height, width = frame_uint8.shape
    total_pixels = height * width
    logging.info(f"📐 Image dimensions: {width}x{height} ({total_pixels:,} pixels)")
    
    # STRATEGY 1: Corner Analysis (DEBUG)
    corner_size = min(20, height//8, width//8)
    logging.info(f"🏠 Corner analysis with size: {corner_size}x{corner_size}")
    
    corners = [
        frame_uint8[0:corner_size, 0:corner_size],           # Top-left
        frame_uint8[0:corner_size, -corner_size:],           # Top-right  
        frame_uint8[-corner_size:, 0:corner_size],           # Bottom-left
        frame_uint8[-corner_size:, -corner_size:]            # Bottom-right
    ]
    
    corner_means = [np.mean(corner) for corner in corners]
    corner_pixels = np.concatenate([corner.flatten() for corner in corners])
    corner_mean = np.mean(corner_pixels)
    
    logging.info(f"🏠 Corner means: {corner_means}")
    logging.info(f"🏠 Overall corner mean: {corner_mean:.1f}")
    
    # STRATEGY 2: Edge Analysis (DEBUG)
    edge_pixels = []
    edge_pixels.extend(frame_uint8[0, :].flatten())   # Top row
    edge_pixels.extend(frame_uint8[-1, :].flatten())  # Bottom row
    edge_pixels.extend(frame_uint8[:, 0].flatten())   # Left column
    edge_pixels.extend(frame_uint8[:, -1].flatten())  # Right column
    
    edge_pixels = np.array(edge_pixels)
    edge_mean = np.mean(edge_pixels)
    dark_edge_count = np.sum(edge_pixels < 50)
    bright_edge_count = np.sum(edge_pixels > 200)
    total_edge_pixels = len(edge_pixels)
    
    dark_edge_ratio = dark_edge_count / total_edge_pixels
    bright_edge_ratio = bright_edge_count / total_edge_pixels
    
    logging.info(f"🔲 Edge analysis:")
    logging.info(f"   Edge mean: {edge_mean:.1f}")
    logging.info(f"   Dark edges (<50): {dark_edge_count}/{total_edge_pixels} ({dark_edge_ratio:.1%})")
    logging.info(f"   Bright edges (>200): {bright_edge_count}/{total_edge_pixels} ({bright_edge_ratio:.1%})")
    
    # STRATEGY 3: Overall Statistics (DEBUG)
    image_mean = np.mean(frame_uint8)
    dark_pixels = np.sum(frame_uint8 < 50)
    bright_pixels = np.sum(frame_uint8 > 200)
    mid_pixels = total_pixels - dark_pixels - bright_pixels
    
    logging.info(f"📊 Overall statistics:")
    logging.info(f"   Image mean: {image_mean:.1f}")
    logging.info(f"   Dark pixels (<50): {dark_pixels:,} ({dark_pixels/total_pixels:.1%})")
    logging.info(f"   Bright pixels (>200): {bright_pixels:,} ({bright_pixels/total_pixels:.1%})")
    logging.info(f"   Mid-range pixels: {mid_pixels:,} ({mid_pixels/total_pixels:.1%})")
    
    # STRATEGY 4: Histogram Analysis (DEBUG)
    hist, bins = np.histogram(frame_uint8, bins=50, range=(0, 255))
    peak_bins = []
    for i in range(1, len(hist) - 1):
        if hist[i] > hist[i-1] and hist[i] > hist[i+1] and hist[i] > np.max(hist) * 0.05:
            peak_bins.append((bins[i], hist[i]))
    
    logging.info(f"📈 Histogram analysis:")
    logging.info(f"   Found {len(peak_bins)} peaks: {[(int(b), int(h)) for b, h in peak_bins]}")
    
    # DECISION LOGIC WITH DEBUG
    confidence = 0
    background_type = "black"  # Default
    decision_factors = []
    
    logging.info(f"\n  DECISION PROCESS:")
    
    # Rule 1: Corner analysis
    if corner_mean < 50:
        background_type = "black"
        confidence += 40
        decision_factors.append(f"  Dark corners ({corner_mean:.1f} < 50) → BLACK (+40)")
    elif corner_mean > 200:
        background_type = "white"
        confidence += 40
        decision_factors.append(f"  Bright corners ({corner_mean:.1f} > 200) → WHITE (+40)")
    else:
        decision_factors.append(f"⚠️ Neutral corners ({corner_mean:.1f}) → No strong signal")
    
    # Rule 2: Edge consistency
    if dark_edge_ratio > 0.7:
        if background_type == "black":
            confidence += 30
            decision_factors.append(f"  Dark edges ({dark_edge_ratio:.1%}) support BLACK (+30)")
        else:
            confidence += 15
            decision_factors.append(f"⚠️ Dark edges ({dark_edge_ratio:.1%}) weak support (+15)")
    elif bright_edge_ratio > 0.7:
        if background_type == "white":
            confidence += 30
            decision_factors.append(f"  Bright edges ({bright_edge_ratio:.1%}) support WHITE (+30)")
        else:
            confidence += 15
            decision_factors.append(f"⚠️ Bright edges ({bright_edge_ratio:.1%}) weak support (+15)")
    else:
        decision_factors.append(f"⚠️ Mixed edges (dark: {dark_edge_ratio:.1%}, bright: {bright_edge_ratio:.1%})")
    
    # Rule 3: Overall image brightness
    if image_mean < 80:
        if background_type == "black":
            confidence += 10
            decision_factors.append(f"  Dark image ({image_mean:.1f} < 80) supports BLACK (+10)")
    elif image_mean > 180:
        if background_type == "white":
            confidence += 10
            decision_factors.append(f"  Bright image ({image_mean:.1f} > 180) supports WHITE (+10)")
    else:
        decision_factors.append(f"⚠️ Mid-brightness image ({image_mean:.1f})")
    
    # Clamp confidence
    confidence = min(100, max(0, confidence))
    
    logging.info(f"\n📋 DECISION FACTORS:")
    for factor in decision_factors:
        logging.info(f"   {factor}")
    
    logging.info(f"\n  FINAL DECISION:")
    logging.info(f"   Background Type: {background_type.upper()}")
    logging.info(f"   Confidence: {confidence}%")
    logging.info(f"   Reasoning: {len(decision_factors)} factors analyzed")
    
    # Calculate background pixels for result
    if background_type == "black":
        background_pixels = dark_pixels
    else:
        background_pixels = bright_pixels
    
    background_percentage = (background_pixels / total_pixels) * 100
    
    result = {
        "background_type": background_type,
        "confidence": int(confidence),
        "background_pixels": int(background_pixels),
        "object_pixels": int(total_pixels - background_pixels),
        "background_percentage": float(background_percentage),
        "total_pixels": int(total_pixels),
        "debug_info": {
            "corner_mean": float(corner_mean),
            "edge_mean": float(edge_mean),
            "image_mean": float(image_mean),
            "dark_edge_ratio": float(dark_edge_ratio),
            "bright_edge_ratio": float(bright_edge_ratio),
            "decision_factors": decision_factors
        }
    }
    
    logging.info(f"📊 RESULT: {result}")
    logging.info(f"  === END BACKGROUND ANALYSIS ===\n")
    
    return result

def convert_to_black_background(frame_data: np.ndarray, current_bg: str = "auto") -> np.ndarray:
    """
    Convert frame to black background (invert if white background)
    
    Args:
        frame_data: Original frame data
        current_bg: "black", "white", or "auto" for auto-detection
        
    Returns:
        Frame data with black background
    """
    if frame_data is None or frame_data.size == 0:
        return frame_data
    
    # Auto-detect background if needed
    if current_bg == "auto":
        analysis = analyze_background_type(frame_data)
        current_bg = analysis["background_type"]
        logging.info(f"  Auto-detected background: {current_bg} (confidence: {analysis['confidence']}%)")
    
    # If already black background, return as-is
    if current_bg == "black":
        logging.info(f"  Keeping black background")
        return frame_data
    
    # If white background, invert to make it black background  
    if current_bg == "white":
        logging.info(f"🔄 Converting white background to black (inverting)")
        
        # Normalize to uint8 if needed
        if frame_data.dtype != np.uint8:
            frame_norm = (frame_data - frame_data.min()) / max(frame_data.max() - frame_data.min(), 1)
            frame_uint8 = (frame_norm * 255).astype(np.uint8)
        else:
            frame_uint8 = frame_data.copy()
        
        # Invert: white becomes black, black becomes white
        inverted = 255 - frame_uint8
        logging.info(f"  White background inverted to black")
        return inverted
    
    return frame_data

# Backward compatibility
def analyze_pixel_distribution(frame_data: np.ndarray) -> Dict[str, any]:
    """Backward compatibility wrapper"""
    analysis = analyze_background_type(frame_data)
    
    # Convert to old format for compatibility
    return {
        "white_pixels": analysis["background_pixels"] if analysis["background_type"] == "white" else analysis["object_pixels"],
        "black_pixels": analysis["background_pixels"] if analysis["background_type"] == "black" else analysis["object_pixels"],
        "total_pixels": analysis["total_pixels"],
        "white_percentage": analysis["background_percentage"] if analysis["background_type"] == "white" else (100 - analysis["background_percentage"]),
        "black_percentage": analysis["background_percentage"] if analysis["background_type"] == "black" else (100 - analysis["background_percentage"]),
        "suggested_background": analysis["background_type"],
        "confidence": analysis["confidence"]
    }
