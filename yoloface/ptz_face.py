import ptz as ptz # import all functions from ptz module
import time
import cv2
from dict2xml import dict2xml
import subprocess
import shlex
import rtsp
import torch
from dict2xml import dict2xml
from PIL import Image
import sys
#import Yolodetector function from yoloface module
from face_detector import YoloDetector
import numpy as np



user_credentials = 'admin:password123'
camera_ip = "10.0.6.16" #'192.168.1.99'
rtsp_url = 'rtsp://' + str(user_credentials) + "@" + str(camera_ip)
camera_stream_number = 1
point_coord = (0, 0)
model = YoloDetector(target_size=640, device = "cpu", min_face= 90)
last_det = time.perf_counter()
# Initialize camera
with rtsp.Client(rtsp_server_uri = rtsp_url) as client:
    frame = client.read(raw = True)
    while True:
        start_time = time.time()
        if frame is not None:
            h, w, _ = frame.shape
            img_w, img_h = w, h
            centre_coord = (img_w // 2, img_h // 2)
            inflated_centre_coord = ptz.uncertainty_range(centre_coord, 20)
                
            if time.perf_counter() - last_det > loop_time:
                bboxes,points = model.predict(np.array(frame))
                last_det = time.perf_counter()
                print(bboxes)
            
                if len(bboxes[0]) > 0:
                    print(f'Detected {len(bboxes)}')
                    # Select random person
                    chosen = bboxes[0][0]
                    x1, y1, x2, y2= list(chosen)
                    y1 = h - y1
                    y2 = h - y2
                    person_cx, person_cy = (x2 + x1) // 2, (y2 + y1) // 2
                    #adjust y to start from the bottom of the image
                    person_center =[person_cx, person_cy]
                    top_left = [x1,y1]
                    btm_right = [x2,y2]
                    person_hy = y2 - y1
                    person_hx = x2 - x1
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    y_top, y_btm = h - y1, y2
                    x_left, x_right = x1, w - x2
                    api_start = time.time()
                    if not ptz.is_person_in_center(centre_coord, person_center, inflated_centre_coord):
                        ptz.move_towards(centre_coord, person_center, 3, user_credentials, 1, camera_ip)

                    if ptz.is_person_in_center(centre_coord, person_center, inflated_centre_coord):
                        print('Person in center')
                        ptz.move_towards(centre_coord, person_center, 0, user_credentials, 1, camera_ip)
                    api_time = time.time() - api_start
                    print(f'API time: {api_time}')

                







            cv2.imshow('image', frame)
            # If user presses 'q', exit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        loop_time = time.time() - start_time
        frame = client.read(raw = True)
