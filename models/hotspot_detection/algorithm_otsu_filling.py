from PIL import Image
import cv2
import numpy as np

from skimage.morphology import binary_dilation, disk

DICT_HOTSPOT_ID = {
    0: "background",
    1: "normal",
    2: "abnormal"
}

def enhance_CLAHE(image, limit=1.5, tile_grid_size=(8, 8)):
    if image.dtype != np.uint8:
        image = normalize_image(image, (0, 255)).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=limit, tileGridSize=tile_grid_size)
    return clahe.apply(image)

def normalize_image(image, range=(0, 1)):
    imin, imax = image.min(), image.max()
    rmin, rmax = range
    if imax - imin == 0:
        return np.full_like(image, rmin, dtype=np.float32)
    return ((image - imin) / (imax - imin)) * (rmax - rmin) + rmin

def threshold_otsu(image, nbins=0.01):
    if image.ndim != 2:
        print("must be a grayscale image.")
        return
    if np.min(image) == np.max(image):
        print("the image must have multiple colors")
        return

    all_colors = image.flatten()
    total_weight = len(all_colors)
    thresholds = np.arange(np.min(image) + nbins, np.max(image) - nbins, nbins)

    best_thresh = -1
    min_variance = float('inf')

    for t in thresholds:
        bg = all_colors[all_colors < t]
        fg = all_colors[all_colors >= t]

        w_bg = len(bg) / total_weight
        w_fg = len(fg) / total_weight

        var_bg = np.var(bg) if len(bg) > 0 else 0
        var_fg = np.var(fg) if len(fg) > 0 else 0

        wcv = w_bg * var_bg + w_fg * var_fg
        if wcv < min_variance:
            min_variance = wcv
            best_thresh = t

    return best_thresh

def color_pixels_within_bounding_boxes(img, list_bb):
    if img.ndim == 2:
        height, width = img.shape
    elif img.ndim == 3 and img.shape[2] == 1:
        height, width = img.shape[:2]
        img = img.squeeze()
    else:
        raise ValueError(f"Unsupported image shape: {img.shape}")

    if height != 1024 or width != 256:
        return None

    mask = np.zeros((height, width), dtype=np.uint8)

    for bbox in list_bb:
        x_min, y_min, x_max, y_max = map(int, bbox['bbox'])
        label = bbox['label']

        if (
            x_min < 0 or y_min < 0 or
            x_max > width or y_max > height or
            x_min >= x_max or y_min >= y_max
        ):
            return None

        grayscale_matrix = img[y_min:y_max, x_min:x_max]
        otsu_thresh = threshold_otsu(grayscale_matrix, nbins=10)
        binary_mask = grayscale_matrix > otsu_thresh
        dilated_mask = binary_dilation(binary_mask, disk(1))

        label_id = 1 if label.lower() == 'normal' else 2

        for x in range(x_min, x_max):
            for y in range(y_min, y_max):
                mx, my = x - x_min, y - y_min
                if my < dilated_mask.shape[0] and mx < dilated_mask.shape[1] and dilated_mask[my, mx]:
                    mask[y, x] = label_id

        for x in range(max(3, x_min + 3), min(width - 3, x_max - 3)):
            for y in range(max(3, y_min + 3), min(height - 3, y_max - 3)):
                if mask[y, x] == 0:
                    neighbors = []
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),
                                   (-2,0),(2,0),(0,-2),(0,2),
                                   (-3,0),(3,0),(0,-3),(0,3)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            neighbors.append(mask[ny, nx])
                    if neighbors.count(label_id) >= 4:
                        mask[y, x] = label_id

    return mask