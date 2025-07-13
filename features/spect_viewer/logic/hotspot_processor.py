import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from skimage.filters import threshold_otsu
from skimage.morphology import binary_dilation, disk


def extract_grayscale_matrix(image_file: str, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """
    Extract grayscale matrix from image within bounding box.
    
    Args:
        image_file: Path to image file
        bbox: Tuple of (x_min, y_min, x_max, y_max)
    
    Returns:
        np.ndarray: Grayscale matrix of the region
    """
    with Image.open(image_file) as img:
        # Convert to grayscale if not already
        if img.mode != 'L':
            img = img.convert('L')
        
        x_min, y_min, x_max, y_max = bbox
        cropped = img.crop((x_min, y_min, x_max, y_max))
        return np.array(cropped)


def threshold_otsu_impl(grayscale_matrix: np.ndarray, nbins: int = 256) -> float:
    """
    Custom Otsu threshold implementation.
    
    Args:
        grayscale_matrix: Input grayscale image as numpy array
        nbins: Number of bins for histogram
    
    Returns:
        float: Optimal threshold value
    """
    # Calculate histogram
    hist, bin_edges = np.histogram(grayscale_matrix.flatten(), bins=nbins, range=(0, 256))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Calculate weights and means
    total_pixels = grayscale_matrix.size
    cumsum_hist = np.cumsum(hist)
    cumsum_weighted = np.cumsum(hist * bin_centers)
    
    # Calculate between-class variance for each threshold
    variances = []
    for i in range(1, len(hist)):
        # Weight of background class
        w0 = cumsum_hist[i-1] / total_pixels
        # Weight of foreground class
        w1 = 1 - w0
        
        if w0 == 0 or w1 == 0:
            variances.append(0)
            continue
            
        # Mean of background class
        mu0 = cumsum_weighted[i-1] / cumsum_hist[i-1] if cumsum_hist[i-1] > 0 else 0
        # Mean of foreground class
        mu1 = (cumsum_weighted[-1] - cumsum_weighted[i-1]) / (total_pixels - cumsum_hist[i-1]) if (total_pixels - cumsum_hist[i-1]) > 0 else 0
        
        # Between-class variance
        variance = w0 * w1 * (mu0 - mu1) ** 2
        variances.append(variance)
    
    # Find threshold that maximizes between-class variance
    optimal_idx = np.argmax(variances)
    return bin_centers[optimal_idx]


def parse_xml_annotations(xml_file: str) -> List[Tuple[int, int, int, int, str]]:
    """
    Parse XML file to extract bounding box annotations.
    
    Args:
        xml_file: Path to XML annotation file
    
    Returns:
        List of tuples: (x_min, y_min, x_max, y_max, label)
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        bounding_boxes = []
        print("root", root.findall('.//object'))
        # Try different XML structures
        # Structure 1: <annotation><object><bndbox>
        for obj in root.findall('.//object'):
            bndbox = obj.find('bndbox')
            if bndbox is not None:
                x_min = int(float(bndbox.find('xmin').text))
                y_min = int(float(bndbox.find('ymin').text))
                x_max = int(float(bndbox.find('xmax').text))
                y_max = int(float(bndbox.find('ymax').text))
                
                name_elem = obj.find('name')
                label = name_elem.text if name_elem is not None else 'Unknown'
                
                bounding_boxes.append((x_min, y_min, x_max, y_max, label))
        
        # Structure 2: Direct bounding box elements
        if not bounding_boxes:
            for bbox in root.findall('.//bounding_box'):
                x_min = int(float(bbox.get('x_min', bbox.get('xmin', 0))))
                y_min = int(float(bbox.get('y_min', bbox.get('ymin', 0))))
                x_max = int(float(bbox.get('x_max', bbox.get('xmax', 0))))
                y_max = int(float(bbox.get('y_max', bbox.get('ymax', 0))))
                label = bbox.get('label', bbox.get('class', 'Unknown'))
                
                bounding_boxes.append((x_min, y_min, x_max, y_max, label))
        
        return bounding_boxes
    
    except Exception as e:
        print(f"Error parsing XML file {xml_file}: {e}")
        return []


def create_hotspot_mask(image_file: str, bounding_boxes: List[Tuple[int, int, int, int, str]], 
                       patient_id: str, view: str, output_dir: str = None) -> Tuple[np.ndarray, Image.Image]:
    """
    Create hotspot mask and overlayed image based on Otsu threshold and morphological operations.
    
    Args:
        image_file: Path to input image
        bounding_boxes: List of bounding boxes with labels
        patient_id: Patient ID for naming output files
        view: View type (ant/post) for naming output files
        output_dir: Directory to save mask files
    
    Returns:
        Tuple of (mask_array, overlayed_image): Hotspot mask and overlayed image
    """
    with Image.open(image_file) as img:
        # Convert to grayscale for mask creation
        gray_img = img.convert('L')
        gray_array = np.array(gray_img)
        
        # Convert to RGB for overlay
        rgb_img = img.convert('RGB')
        rgb_array = np.array(rgb_img)
        
        width, height = img.size
        
        # Initialize mask with black background
        mask = np.zeros((height, width), dtype=np.uint8)
        
        for bbox in bounding_boxes:
            x_min, y_min, x_max, y_max, label = bbox
            
            # Ensure coordinates are within image bounds
            x_min = max(0, min(x_min, width - 1))
            y_min = max(0, min(y_min, height - 1))
            x_max = max(x_min + 1, min(x_max, width))
            y_max = max(y_min + 1, min(y_max, height))
            
            # Extract grayscale matrix for the bounding box
            grayscale_matrix = extract_grayscale_matrix(image_file, (x_min, y_min, x_max, y_max))
            
            if grayscale_matrix.size == 0:
                continue
            
            # Apply Otsu threshold
            otsu_thresh = threshold_otsu_impl(grayscale_matrix, nbins=10)
            
            # Create binary mask with Otsu threshold
            binary_mask = grayscale_matrix > otsu_thresh
            
            # Dilate mask to fill holes
            dilated_mask = binary_dilation(binary_mask, disk(1))
            
            # Set mask values based on label
            if label.lower() in ['abnormal', 'hotspot', 'positive']:
                mask_value = 255  # White for abnormal (hotspot)
            elif label.lower() in ['normal', 'negative']:
                mask_value = 128  # Gray for normal
            else:
                mask_value = 64   # Dark gray for unknown
            
            # Apply mask to the region
            for x in range(x_min, x_max):
                for y in range(y_min, y_max):
                    # Calculate mask position
                    mask_x = x - x_min
                    mask_y = y - y_min
                    
                    # Set mask value if within dilated mask
                    if mask_y < dilated_mask.shape[0] and mask_x < dilated_mask.shape[1]:
                        if dilated_mask[mask_y, mask_x]:
                            mask[y, x] = mask_value
            
            # Fill remaining holes using neighborhood checking
            for x in range(max(1, x_min), min(width - 1, x_max)):
                for y in range(max(1, y_min), min(height - 1, y_max)):
                    # Check various neighborhood patterns
                    neighbors = [
                        (x-1, y), (x+1, y), (x, y-1), (x, y+1),
                        (x-2, y), (x+2, y), (x, y-2), (x, y+2),
                        (x-3, y), (x+3, y), (x, y-3), (x, y+3)
                    ]
                    
                    # Count matching neighbors
                    matching_neighbors = 0
                    for nx, ny in neighbors[:4]:  # Check direct neighbors first
                        if 0 <= nx < width and 0 <= ny < height:
                            if mask[ny, nx] == mask_value:
                                matching_neighbors += 1
                    
                    # Fill if surrounded by colored pixels
                    if matching_neighbors >= 3:
                        mask[y, x] = mask_value
        
        # Save mask as PNG
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            mask_filename = f"{patient_id}_{view}_hotspot_mask.png"
            mask_path = output_path / mask_filename
            Image.fromarray(mask).save(mask_path)
            print(f"Hotspot mask saved: {mask_path}")
        
        # Create overlayed image
        overlayed_array = rgb_array.copy()
        
        # Apply color overlay where mask is non-black
        for bbox in bounding_boxes:
            x_min, y_min, x_max, y_max, label = bbox
            
            # Ensure coordinates are within image bounds
            x_min = max(0, min(x_min, width - 1))
            y_min = max(0, min(y_min, height - 1))
            x_max = max(x_min + 1, min(x_max, width))
            y_max = max(y_min + 1, min(y_max, height))
            
            # Define overlay color based on label
            if label.lower() in ['abnormal', 'hotspot', 'positive']:
                overlay_color = np.array([255, 0, 0])  # Red for abnormal
            elif label.lower() in ['normal', 'negative']:
                overlay_color = np.array([255, 241, 188])  # Light cream for normal
            else:
                overlay_color = np.array([0, 255, 0])  # Green for unknown
            
            # Apply overlay with transparency
            for y in range(y_min, y_max):
                for x in range(x_min, x_max):
                    if mask[y, x] > 0:  # Non-black pixels in mask
                        # Blend original image with overlay color (50% transparency)
                        alpha = 0.5
                        overlayed_array[y, x] = (
                            alpha * overlay_color + 
                            (1 - alpha) * overlayed_array[y, x]
                        ).astype(np.uint8)
        
        overlayed_image = Image.fromarray(overlayed_array)
        
        return mask, overlayed_image


def color_pixels_within_bounding_boxes(image_file: str, bounding_boxes: List[Tuple[int, int, int, int, str]], 
                                     output_file: str = None, colormap: str = 'jet') -> Image.Image:
    """
    DEPRECATED: Use create_hotspot_mask instead.
    Color pixels within bounding boxes based on Otsu threshold and morphological operations.
    
    Args:
        image_file: Path to input image
        bounding_boxes: List of bounding boxes with labels
        output_file: Optional output file path
        colormap: Matplotlib colormap name
    
    Returns:
        PIL.Image: Processed image with colored hotspots
    """
    with Image.open(image_file) as img:
        # Convert to RGB for coloring
        img = img.convert('RGB')
        pixels = img.load()
        width, height = img.size
        
        # Colormap setup
        cmap = plt.get_cmap(colormap)
        norm = mcolors.Normalize(vmin=0, vmax=255)
        
        for bbox in bounding_boxes:
            x_min, y_min, x_max, y_max, label = bbox
            
            # Ensure coordinates are within image bounds
            x_min = max(0, min(x_min, width - 1))
            y_min = max(0, min(y_min, height - 1))
            x_max = max(x_min + 1, min(x_max, width))
            y_max = max(y_min + 1, min(y_max, height))
            
            # Extract grayscale matrix for the bounding box
            grayscale_matrix = extract_grayscale_matrix(image_file, (x_min, y_min, x_max, y_max))
            
            if grayscale_matrix.size == 0:
                continue
            
            # Apply Otsu threshold
            otsu_thresh = threshold_otsu_impl(grayscale_matrix, nbins=10)
            
            # Create binary mask with Otsu threshold
            binary_mask = grayscale_matrix > otsu_thresh
            
            # Dilate mask to fill holes
            dilated_mask = binary_dilation(binary_mask, disk(1))
            
            # Color pixels based on label and dilated mask
            for x in range(x_min, x_max):
                for y in range(y_min, y_max):
                    # Calculate mask position
                    mask_x = x - x_min
                    mask_y = y - y_min
                    
                    # Color if within dilated mask
                    if mask_y < dilated_mask.shape[0] and mask_x < dilated_mask.shape[1]:
                        if dilated_mask[mask_y, mask_x]:
                            if label.lower() in ['abnormal', 'hotspot', 'positive']:
                                color = (255, 0, 0)  # Red for abnormal
                            elif label.lower() in ['normal', 'negative']:
                                color = (255, 241, 188)  # Light cream for normal
                            else:
                                color = (0, 255, 0)  # Green for unknown
                            
                            pixels[x, y] = color
            
            # Fill remaining holes using neighborhood checking
            for x in range(max(1, x_min), min(width - 1, x_max)):
                for y in range(max(1, y_min), min(height - 1, y_max)):
                    if label.lower() in ['abnormal', 'hotspot', 'positive']:
                        color = (255, 0, 0)
                    elif label.lower() in ['normal', 'negative']:
                        color = (255, 241, 188)
                    else:
                        color = (0, 255, 0)
                    
                    # Check various neighborhood patterns
                    neighbors = [
                        (x-1, y), (x+1, y), (x, y-1), (x, y+1),
                        (x-2, y), (x+2, y), (x, y-2), (x, y+2),
                        (x-3, y), (x+3, y), (x, y-3), (x, y+3)
                    ]
                    
                    # Count matching neighbors
                    matching_neighbors = 0
                    for nx, ny in neighbors[:4]:  # Check direct neighbors first
                        if 0 <= nx < width and 0 <= ny < height:
                            if pixels[nx, ny] == color:
                                matching_neighbors += 1
                    
                    # Fill if surrounded by colored pixels
                    if matching_neighbors >= 3:
                        pixels[x, y] = color
        
        # Save if output file specified
        if output_file:
            img.save(output_file)
        
        # Delete other pixel colors
        return img


class HotspotProcessor:
    """
    Main class for processing hotspot images with XML annotations.
    """
    
    def __init__(self, temp_dir: str = "data/tmp/hotspot_temp"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
    
    def process_image_with_xml(self, image_path: str, xml_path: str, patient_id: str = None, view: str = None) -> Optional[Image.Image]:
        """
        Process an image with its corresponding XML annotation file.
        
        Args:
            image_path: Path to the source image
            xml_path: Path to the XML annotation file
            patient_id: Patient ID for naming output files
            view: View type (ant/post) for naming output files
        
        Returns:
            PIL.Image or None: Processed image with hotspots overlayed
        """
        if not Path(image_path).exists():
            print(f"Image file not found: {image_path}")
            return None
        
        if not Path(xml_path).exists():
            print(f"XML file not found: {xml_path}")
            return None
        
        # Parse XML annotations
        bounding_boxes = parse_xml_annotations(xml_path)
        
        if not bounding_boxes:
            print(f"No bounding boxes found in {xml_path}")
            return None
        
        print("hotspot processing started")
        
        # Extract patient_id and view from paths if not provided
        if patient_id is None:
            patient_id = Path(image_path).parent.name
        if view is None:
            filename_lower = Path(image_path).stem.lower()
            view = "post" if "post" in filename_lower else "ant"
        
        # Process image with bounding boxes using new method
        try:
            mask, overlayed_image = create_hotspot_mask(
                image_path, 
                bounding_boxes,
                patient_id,
                view,
                output_dir=str(Path(image_path).parent)  # Save mask in same directory as image
            )
            print("Image mask saved at:", Path(image_path).parent)
            print("hotspot processing completed")
            return overlayed_image
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            return None
    
    def find_xml_for_image(self, image_path: str, xml_dir: str = None) -> Optional[str]:
        """
        Find corresponding XML file for an image.
        
        Args:
            image_path: Path to the image file
            xml_dir: Directory to search for XML files (defaults to same dir as image)
        
        Returns:
            str or None: Path to XML file if found
        """
        image_path = Path(image_path)
        
        if xml_dir is None:
            xml_dir = image_path.parent
        else:
            xml_dir = Path(xml_dir)
        
        # Try different naming conventions
        possible_names = [
            image_path.stem + ".xml",
            image_path.stem + "_annotations.xml",
            image_path.stem + "_bbox.xml",
            "annotations_" + image_path.stem + ".xml"
        ]
        
        for name in possible_names:
            xml_path = xml_dir / name
            if xml_path.exists():
                return str(xml_path)
        
        return None
    
    def process_image_auto_xml(self, image_path: str, xml_dir: str = None) -> Optional[Image.Image]:
        """
        Process image and automatically find corresponding XML file.
        
        Args:
            image_path: Path to the source image
            xml_dir: Directory to search for XML files
        
        Returns:
            PIL.Image or None: Processed image with hotspots overlayed
        """
        xml_path = self.find_xml_for_image(image_path, xml_dir)
        
        if xml_path is None:
            print(f"No XML annotation file found for {image_path}")
            return None
        
        return self.process_image_with_xml(image_path, xml_path)
    
    
    