import ptz as ptz # import all functions from ptz module
import time
import cv2
import rtsp
import torch


point_coord = (0, 0)
user_credentials = 'admin:password123'
camera_ip = "10.0.6.16"
rtsp_url = 'rtsp://' + str(user_credentials) + "@" + str(camera_ip)
camera_stream_number = 1
camera_info = ptz.camera_info_packager(user_credentials, camera_ip, camera_stream_number)


model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)
last_det = time.perf_counter()
no_person = 0
# Initialize camera
with rtsp.Client(rtsp_server_uri = rtsp_url) as client:
    frame = client.read(raw = True)
    ptz.reset_hikcamera(0,0, user_credentials, camera_ip)
    while True:
        loop_start = time.time()
        if frame is not None:
            h, w, _ = frame.shape
            img_w, img_h = w, h
            frame_shape = [img_w, img_h]
            centre_coord = (img_w // 2, img_h // 2)
            inflated_centre = ptz.uncertainty_range(centre_coord, 20)
                
            if time.perf_counter() - last_det > loop_time:
                inference_start = time.time()
                persons = ptz.get_persons(model, frame)
                last_det = time.perf_counter()
                inference_time = time.time() - inference_start
                print(f'Inference time: {inference_time}')
            
                if len(persons) > 0:
                    print(f'Detected {len(persons)}')
                    # Select random person
                    chosen = persons[0]
                    x1, y1, x2, y2, conf, label = list(chosen)
                    y1 = h - y1
                    y2 = h - y2
                    person_cx, person_cy = (x2 + x1) // 2, (y2 + y1) // 2
                    #adjust y to start from the bottom of the image

                    person_center =[person_cx, person_cy - 0.25*(y2-y1)]
                    top_left = [x1,y1]
                    btm_right = [x2,y2]
                    person_hy = y2 - y1
                    person_hx = x2 - x1
                    det_box_size = [person_hx, person_hy]
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    
                    y_top, y_btm = h - y1, y2
                    x_left, x_right = x1, w - x2
                    frame_det_distance = [x_left, x_right, y_btm, y_top]
                    
                    API_start = time.time()
                    if conf > 0.60 and not ptz.is_person_in_center(centre_coord, person_center, inflated_centre):
                        if ptz.zoom_limiter(frame_shape, det_box_size, 0.5):
                            print('Zooming out')
                            ptz.zoom_in(-1, camera_info)
                        else:
                            ptz.move_towards(centre_coord, person_center, 3, camera_info)
                            #check_x, check_y, check_z = ptz.query_hikcamera_pos(user_credentials, camera_ip, camera_stream_number)
                            #print(f'Person not in center, moving towards center. Current position: {check_x}, {check_y}, {check_z}')
                    api_time = time.time() - API_start
                    print(f'API time: {api_time}')
                    if ptz.is_person_in_center(centre_coord, person_center, inflated_centre):
                        print('Person in center')
                        ptz.zoom_in(1, camera_info)
                else:
                    print('No person detected')
                    ptz.zoom_in(0, camera_info)
                    #_,_,zoom_value = ptz.query_hikcamera_pos(user_credentials, camera_ip, camera_stream_number)
                    #print(zoom_value)



            cv2.imshow('image', frame)
            # If user presses 'q', exit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        frame = client.read(raw = True)
        loop_time = time.time() - loop_start
        print(f'Loop time: {loop_time}')
