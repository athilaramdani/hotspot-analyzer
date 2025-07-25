from ultralytics import YOLO
import cv2
import matplotlib.pyplot as plt

PATH_MAIN = "./models"
PATH_MODEL = PATH_MAIN + "/model_detection_hs_yolov8.pt"
model = YOLO(PATH_MODEL)

def inference_detection(path_image):
    result = model(path_image)[0]

    boxes = result.boxes
    xyxy = boxes.xyxy.cpu().numpy()
    conf = boxes.conf.cpu().numpy()
    cls = boxes.cls.cpu().numpy().astype(int)
    labels = [result.names[c] for c in cls]

    results = []
    for i in range(len(xyxy)):
        results.append({
            "label": labels[i],
            "class_id": int(cls[i]),
            "confidence": float(conf[i]),
            "bbox": [float(x) for x in xyxy[i]]
        })

    return results