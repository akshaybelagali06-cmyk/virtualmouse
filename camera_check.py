import cv2

print("OpenCV:", cv2.__version__)

for index in range(6):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if cap.isOpened():
        ok, frame = cap.read()
        if ok and frame is not None:
            height, width = frame.shape[:2]
            print(f"Camera {index}: WORKING ({width}x{height})")
        else:
            print(f"Camera {index}: opens, but cannot read frames")
    else:
        print(f"Camera {index}: unavailable")
    cap.release()
