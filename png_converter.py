#!F:\projek dosen\prototype riset\hotspot-analyzer\png_converter.py
"""
TELPLASTINA DICOM to PNG Converter
Simple converter to extract frames from DICOM and save as PNG files

Usage:
   python dicom_to_png.py input.dcm
   python dicom_to_png.py input.dcm --output /path/to/output/
   python dicom_to_png.py input.dcm --prefix patient001
"""

import sys
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import pydicom

def normalize_frame_to_uint8(frame: np.ndarray) -> np.ndarray:
   """
   Normalize DICOM frame to uint8 for PNG saving
   Same algorithm as _save_original_frame_png()
   """
   if frame.dtype != np.uint8:
       # Convert to float32 for calculation
       frame_norm = frame.astype(np.float32)
       
       # Normalize to 0-1 range
       frame_min = frame_norm.min()
       frame_max = frame_norm.max()
       frame_range = max(frame_max - frame_min, 1)  # Avoid division by zero
       
       frame_norm = (frame_norm - frame_min) / frame_range
       
       # Scale to 0-255 and convert to uint8
       frame_uint8 = (frame_norm * 255).astype(np.uint8)
   else:
       frame_uint8 = frame.copy()
   
   return frame_uint8

def extract_view_labels(ds) -> list:
   """
   Extract view labels from DICOM metadata
   Returns list of view names for each frame
   """
   n_frames = int(getattr(ds, "NumberOfFrames", 1))
   labels = [None] * n_frames

   # Method 1: DetectorInformationSequence
   det_seq = getattr(ds, "DetectorInformationSequence", None)
   if det_seq:
       for idx, det in enumerate(det_seq):
           if hasattr(det, "ViewCodeSequence") and idx < n_frames:
               meaning = str(det.ViewCodeSequence[0].CodeMeaning)
               if "ANT" in meaning.upper():
                   labels[idx] = "Anterior"
               elif "POST" in meaning.upper():
                   labels[idx] = "Posterior"
               else:
                   labels[idx] = meaning.strip()

   # Method 2: Root ViewCodeSequence
   if all(lbl is None for lbl in labels) and hasattr(ds, "ViewCodeSequence"):
       view_seq = ds.ViewCodeSequence
       for idx, view_item in enumerate(view_seq):
           if idx >= n_frames:
               break
           if hasattr(view_item, "CodeMeaning"):
               meaning = str(view_item.CodeMeaning)
               if "ANT" in meaning.upper():
                   labels[idx] = "Anterior"
               elif "POST" in meaning.upper():
                   labels[idx] = "Posterior"
               else:
                   labels[idx] = meaning.strip()

   # Method 3: ViewPosition tag
   if all(lbl is None for lbl in labels) and hasattr(ds, "ViewPosition"):
       view_pos = str(ds.ViewPosition)
       if "\\" in view_pos:
           positions = view_pos.split("\\")
           for idx, pos in enumerate(positions):
               if idx >= n_frames:
                   break
               if "ANT" in pos.upper():
                   labels[idx] = "Anterior"
               elif "POST" in pos.upper():
                   labels[idx] = "Posterior"
               else:
                   labels[idx] = pos.strip()

   # Fallback: Smart assumption for bone scan
   if all(lbl is None for lbl in labels):
       if n_frames == 2:
           labels = ["Anterior", "Posterior"]
           print(f"   🎯 Using bone scan assumption: [Anterior, Posterior]")
       else:
           labels = [f"Frame_{i+1}" for i in range(n_frames)]
           print(f"   ⚠️  Generic fallback: {labels}")

   return labels

def convert_dicom_to_png(dicom_path: Path, output_dir: Path = None, prefix: str = None) -> list:
   """
   Convert DICOM file to PNG frames
   
   Args:
       dicom_path: Path to DICOM file
       output_dir: Output directory (default: same as DICOM)
       prefix: Filename prefix (default: DICOM filename)
       
   Returns:
       List of created PNG file paths
   """
   # Validate input
   if not dicom_path.exists():
       raise FileNotFoundError(f"DICOM file not found: {dicom_path}")
   
   if not dicom_path.suffix.lower() in ['.dcm', '.dicom']:
       print(f"⚠️  Warning: File doesn't have .dcm/.dicom extension: {dicom_path}")
   
   # Set output directory
   if output_dir is None:
       output_dir = dicom_path.parent
   else:
       output_dir = Path(output_dir)
       output_dir.mkdir(parents=True, exist_ok=True)
   
   # Set filename prefix
   if prefix is None:
       prefix = dicom_path.stem
   
   print(f"🏥 Processing DICOM: {dicom_path.name}")
   print(f"📁 Output directory: {output_dir}")
   print(f"🏷️  Filename prefix: {prefix}")
   
   try:
       # Read DICOM file
       print("📖 Reading DICOM file...")
       ds = pydicom.dcmread(dicom_path)
       
       # Extract pixel array
       pixel_array = ds.pixel_array
       print(f"🖼️  Pixel array shape: {pixel_array.shape}")
       print(f"🔢 Data type: {pixel_array.dtype}")
       
       # Handle single frame vs multi-frame
       if pixel_array.ndim == 2:
           # Single frame - add frame dimension
           pixel_array = pixel_array[np.newaxis, ...]
           print("📄 Single frame detected, expanding dimensions")
       
       n_frames = pixel_array.shape[0]
       print(f"🎬 Number of frames: {n_frames}")
       
       # Extract view labels
       print("🏷️  Extracting view labels...")
       view_labels = extract_view_labels(ds)
       print(f"📋 View labels: {view_labels}")
       
       # Convert each frame to PNG
       created_files = []
       
       for frame_idx in range(n_frames):
           frame_data = pixel_array[frame_idx]
           view_label = view_labels[frame_idx]
           
           print(f"\n🖼️  Processing Frame {frame_idx + 1}/{n_frames}: {view_label}")
           print(f"   Frame shape: {frame_data.shape}")
           print(f"   Value range: {frame_data.min()} - {frame_data.max()}")
           
           # Normalize frame
           frame_uint8 = normalize_frame_to_uint8(frame_data)
           print(f"   Normalized range: {frame_uint8.min()} - {frame_uint8.max()}")
           
           # Create filename
           safe_view_label = view_label.replace(" ", "_").replace("/", "_")
           if view_label.lower() in ['anterior', 'ant']:
               filename = f"{prefix}_ant_original.png"
           elif view_label.lower() in ['posterior', 'post']:
               filename = f"{prefix}_post_original.png"
           else:
               filename = f"{prefix}_frame_{frame_idx+1}_{safe_view_label}.png"
           
           output_path = output_dir / filename
           
           # Save as PNG
           try:
               pil_image = Image.fromarray(frame_uint8, mode="L")
               pil_image.save(output_path)
               created_files.append(output_path)
               print(f"   ✅ Saved: {filename}")
               print(f"   📏 Image size: {pil_image.size}")
           except Exception as e:
               print(f"   ❌ Failed to save {filename}: {e}")
       
       print(f"\n🎉 Conversion completed!")
       print(f"📊 Created {len(created_files)} PNG files:")
       for file_path in created_files:
           file_size = file_path.stat().st_size / 1024  # KB
           print(f"   📄 {file_path.name} ({file_size:.1f} KB)")
       
       return created_files
       
   except Exception as e:
       print(f"❌ Error processing DICOM file: {e}")
       import traceback
       traceback.print_exc()
       raise

def main():
   """Main function with command line interface"""
   parser = argparse.ArgumentParser(
       description="TELPLASTINA DICOM to PNG Converter",
       formatter_class=argparse.RawDescriptionHelpFormatter,
       epilog="""
Examples:
   python dicom_to_png.py patient001.dcm
   python dicom_to_png.py patient001.dcm --output ./png_output/
   python dicom_to_png.py patient001.dcm --prefix patient001_study1
   python dicom_to_png.py C:/data/scan.dcm --output D:/output/ --prefix scan_20250820
       """
   )
   
   parser.add_argument(
       'dicom_file',
       type=str,
       help='Path to DICOM file to convert'
   )
   
   parser.add_argument(
       '--output', '-o',
       type=str,
       default=None,
       help='Output directory (default: same as DICOM file)'
   )
   
   parser.add_argument(
       '--prefix', '-p',
       type=str,
       default=None,
       help='Output filename prefix (default: DICOM filename)'
   )
   
   parser.add_argument(
       '--verbose', '-v',
       action='store_true',
       help='Verbose output'
   )
   
   args = parser.parse_args()
   
   # Convert arguments
   dicom_path = Path(args.dicom_file)
   output_dir = Path(args.output) if args.output else None
   
   print("🩻 TELPLASTINA DICOM to PNG Converter")
   print("=" * 50)
   
   try:
       created_files = convert_dicom_to_png(
           dicom_path=dicom_path,
           output_dir=output_dir,
           prefix=args.prefix
       )
       
       print("\n✅ Conversion successful!")
       return 0
       
   except FileNotFoundError as e:
       print(f"❌ File not found: {e}")
       return 1
   except Exception as e:
       print(f"❌ Error: {e}")
       if args.verbose:
           import traceback
           traceback.print_exc()
       return 1

if __name__ == "__main__":
   exit(main())