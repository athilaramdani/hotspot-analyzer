# F:\projek dosen\prototype riset\hotspot-analyzer\models\hotspot_detection\pipeline_hs.py
# Import libraries
import cv2
import numpy as np

# Import locally
from inference_detection_hs import inference_detection
from algorithm_otsu_filling import color_pixels_within_bounding_boxes
from features.spect_viewer.logic.inference_classification_hs import inference_classification

def show_image(mask):
    color_image = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)
    color_image[mask == 1] = [0, 255, 0]
    color_image[mask == 2] = [0, 0, 255]
    cv2.imshow("Hotspot Mask", color_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def pipeline_hs(path_raw, path_region):
    image_raw = cv2.imread(path_raw, cv2.IMREAD_GRAYSCALE)

    result_detection = inference_detection(path_raw)

    result_otsu = color_pixels_within_bounding_boxes(image_raw, result_detection) # result otsu adalah mask 256x1024 (bg: 0, normal: 1, abnormal: 2)

    result_classification_np, result_classification_png = inference_classification(path_raw, path_region, result_otsu, result_detection)

    show_image(result_classification_png)

    return result_classification_np, result_classification_png

if __name__ == "__main__":
    PATH_DATASET = "./dataset"

    pipeline_hs(
        PATH_DATASET + "/raw png (cropped+resized)/24_posterior.png",
        PATH_DATASET + "/hotspot segmentation png (cropped+resized)/24_posterior.png"
    )