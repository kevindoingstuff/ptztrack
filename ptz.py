# Description: Functions for PTZ control of Hikvision camera 
from dict2xml import dict2xml
import subprocess
import shlex
import math
import cv2
import numpy as np
from collections import OrderedDict
import time

def uncertainty_range(centre_coord, percentage_inflation = 0.10):
    #check if percentage_inflation is in decimal form and fix if not,
    centre_coord = centre_coord * 2 
    if percentage_inflation > 1:
        percentage_inflation = percentage_inflation / 100
    # Calculate uncertainty range
    uncertainty_range_x = percentage_inflation * centre_coord[0]
    uncertainty_range_y = percentage_inflation * centre_coord[1]
    uncertainty_range = [uncertainty_range_x, uncertainty_range_y] 
    return uncertainty_range

def is_person_in_center(centre_coord, person_center, uncertainty_range):
    # Check if person is in center
    if abs(centre_coord[0] - person_center[0]) < uncertainty_range[0] and abs(centre_coord[1] - person_center[1]) < uncertainty_range[1]:
        return True
    else:
        return False
    
def scale_img(input_size, coord, x_range, y_range):
    coord[1] = input_size[1] - 1 - coord[1]
    coord[0] = int(coord[0]/input_size[0] * (x_range[1] - x_range[0]) + x_range[0])
    coord[1] = int(coord[1]/input_size[1] * (y_range[1] - y_range[0]) + y_range[0])
    return coord

def spherical_to_cartesian(azimuth, elevation, zoom):   # Not working
    # Convert spherical coordinates to cartesian coordinates
    # Azimuth is the angle from the x-axis to the projection of the vector onto the xy-plane
    # Elevation is the angle from the xy-plane to the vector, i.e. angle between the vector and the z-axis
    
    # Normalize and transform into correct range
    transformed_zoom = zoom/10
    # Convert to radians
    azimuth = 0.1 * azimuth * (math.pi / 180)
    elevation = 0.1 * elevation * (math.pi / 180)

    # Calculate x, y, z coordinates
    x = zoom * math.cos(elevation) * math.cos(azimuth)
    y = zoom * math.cos(elevation) * math.sin(azimuth)
    z = zoom * math.sin(elevation)

    return x, y, z

def preprocess_detection_box(input_size, coord_start, coord_end, x_range, y_range):
    coord_start = scale_img(input_size, coord_start, x_range, y_range)
    coord_end = scale_img(input_size, coord_end, x_range, y_range)    
    return coord_start, coord_end

def query_hikcamera_pos(user_credentials, rtsp_id, camera_ip): # returns x,y,z coordinates
    # Query camera azimuth, elevation and zoom information and save to output.txt
    subprocess.run(shlex.split(f'curl -X GET http://{user_credentials}@{rtsp_id}/ISAPI/PTZCtrl/channels/{camera_ip}/status -o output.txt'))
    ### Parse output.txt and return x,y coordinates
    with open('output.txt', 'r') as f:
        lines = f.readlines()
        for line in lines:
            if "elevation" in line:
                elevation = float(line.split('>')[1].split('<')[0])
            elif "azimuth" in line:
                azimuth = float(line.split('>')[1].split('<')[0])
            elif "absoluteZoom" in line:
                zoom = float(line.split('>')[1].split('<')[0])
    
    return spherical_to_cartesian(azimuth, elevation, zoom)
        
def patrol_hikcamera():

    # Patrol camera
    pass

def reposition_hikcamera(top_left, btm_right, user_credentials, camera_ip) -> None:

    # Reposition camera to detection box
    d = {
        'position3D': {
            'StartPoint': {
                'positionX': top_left[0],
                'positionY': top_left[1]
            },
            'EndPoint': {
                'positionX': btm_right[0],
                'positionY': btm_right[1]

            }
        }  
    }
    xml = dict2xml(d)
    with open('position3D.xml', 'w') as f:
        f.write(xml)
    subprocess.run(shlex.split('curl -X PUT -T position3D.xml http://' + user_credentials + '@' + camera_ip + '/ISAPI/PTZCtrl/channels/1/position3D'))

def move_towards(centre_image, centre_target, move_speed, user_credentials, camera_ip, rtsp_ip) -> None:
    # normalize and transform into correct range
    test1_start = time.time()
    speed = (100/10)*move_speed
    #If centre_target not in centre of image, move in the direction
    if  centre_target[0] > centre_image[0]:
        pan_direction = speed
    elif centre_target[0] < centre_image[0]:
        pan_direction = -speed
    else :
        pan_direction = 0

    if centre_target[1] > centre_image[1]:
        tilt_direction = speed
    elif centre_target[1] < centre_image[1]:
        tilt_direction = -speed
    else:
        tilt_direction = 0
    print(f"({centre_image[0]},{centre_image[1]})")
    print(f"moving towards ({centre_target[0]},{centre_target[1]})")

    d = OrderedDict()
    d['PTZData'] = OrderedDict()
    d['PTZData']['pan'] = int(pan_direction)
    d['PTZData']['tilt'] = int(tilt_direction)
    d['PTZData']['zoom'] = int(0)

    xml = dict2xml(d)
    with open('ptzdata.xml', 'w') as f:
        f.write(xml)
    test1 = time.time() - test1_start
    print(f"xml time: {test1}")
    test2_start = time.time()
    subprocess.run(shlex.split(f'curl -X PUT -T ptzdata.xml http://{user_credentials}@{rtsp_ip}/ISAPI/PTZCtrl/channels/{camera_ip}/continuous'))
    test2 = time.time() - test2_start
    print(f"curl time: {test2}")

def zoom_in(zoom_value, user_credentials, camera_ip, camera_id) -> None:
    # Zoom in
    d = OrderedDict()
    d['PTZData'] = OrderedDict()
    d['PTZData']['pan'] = int(0)
    d['PTZData']['tilt'] = int(0)
    d['PTZData']['zoom'] = int(zoom_value)

    xml = dict2xml(d)
    with open('ptzdata.xml', 'w') as f:
        f.write(xml)
    subprocess.run(shlex.split(f'curl -X PUT -T ptzdata.xml http://{user_credentials}@{camera_ip}/ISAPI/PTZCtrl/channels/{camera_id}/continuous'))

def zoom_limiter(frame_shape, det_box_size, zoom_limit_coeff):
    # Check if zoom value is too big
    zoom_bool = False
    excess_zoom_check = [False,False]
    if  frame_shape[0] * zoom_limit_coeff < det_box_size[0]:
        zoom_bool = True
        
    elif frame_shape[1] * zoom_limit_coeff < det_box_size[1]:
        zoom_bool = True
    else:
        zoom_bool = False
    return zoom_bool
              
def refocus_hikcamera(top_left, btm_right,user_credentials, rtsp_ip, camera_ip) -> None:
    # Refocus camera to detection box
    ff = {
        
        'RegionalFocus': {
            'StartPoint': {
                'positionX': top_left[0],
                'positionY': top_left[1]
            },
            'EndPoint': {
                'positionX': btm_right[0],
                'positionY': btm_right[1]

            }
        }  
    }
    xml = dict2xml(ff)
    with open('regional_focus.xml', 'w') as f:
        f.write(xml)
    subprocess.run(shlex.split(f'curl -X PUT -T regional_focus.xml http://{user_credentials}@{rtsp_ip}/ISAPI/PTZCtrl/channels/{camera_ip}/regionalFocus'))

def reexposure_hikcamera(top_left, btm_right, user_credentials, camera_ip) -> None:
    # Reexposure camera to detection box
    ee = {
        'RegionalExposure': {
            'StartPoint': {
                'positionX': top_left[0],
                'positionY': top_left[1]
            },
            'EndPoint': {
                'positionX': btm_right[0],
                'positionY': btm_right[1]

            }
        }  
    }
    xml = dict2xml(ee)
    with open('exposure_region.xml', 'w') as f:
        f.write(xml)
    subprocess.run(shlex.split('curl -X PUT -T exposure_region.xml http://' + user_credentials + '@' + camera_ip + '/ISAPI/PTZCtrl/channels/1/exposureRegion'))

def reset_hikcamera(zoom_speed, focus_mode, user_credentials, camera_ip) -> None:
    def generate_xml():
        # Generate xml file for zoom speed
        d = {
            'PTZSpeed': {
                'zoom': zoom_speed
            }
        }
        xml = dict2xml(d)
        with open('zoom_speed.xml', 'w') as f:
            f.write(xml)
        
        # Generate xml file for focus mode
        ff = {
            'FocusMode': {
                'focusMode': focus_mode
            }
        }
        xml = dict2xml(ff)
        with open('focus_mode.xml', 'w') as f:
            f.write(xml)
        
        # Generate xml file for iris mode
        iris = {
            'IrisMode': {
                'irisMode': 'auto'
            }
        }
        xml = dict2xml(iris)
        with open('iris_mode.xml', 'w') as f:
            f.write(xml)
        
        # Generate xml file for white balance mode
        white_balance = {
            'WhiteBalanceMode': {
                'whiteBalanceMode': 'auto'
            }
        }
        xml = dict2xml(white_balance)
        with open('white_balance_mode.xml', 'w') as f:
            f.write(xml)
        
    generate_xml()
    # Initialization commands 
    #subprocess.run(shlex.split('curl -X PUT -T zoom_speed.xml http://' + user_credentials + '@' + camera_ip + '/ISAPI/' )) ###

    # Reset camera to default position
    subprocess.run(shlex.split('curl -X PUT http://' + user_credentials + '@' + camera_ip + '/ISAPI/PTZCtrl/channels/1/presets/2/goto'))

    # Set camera to auto focus
    #subprocess.run(shlex.split('curl -X PUT -T focus_mode.xml http://' + user_credentials + '@' + camera_ip + '/ISAPI/Imaging/channels/1/focusMode'))

    # Set camera to auto iris
    #subprocess.run(shlex.split('curl -X PUT -T iris_mode.xml http://' + user_credentials + '@' + camera_ip + '/ISAPI/Imaging/channels/1/irisMode'))

    # Set camera to auto white balance
    #subprocess.run(shlex.split(f'curl -X PUT -T white_balance_mode.xml http://' + user_credentials + '@' + camera_ip + '/ISAPI/Imaging/channels/1/whiteBalanceMode'))

######## YOLOv5 Functions ########

def get_persons(model, img):
    results = model(img)
    dets = results.xyxy[0]
    #print(results.pandas().xyxy[0])
    persons = dets[(dets[:,-1] == 0.0) & (dets[:,-2] > 0.5)]
    return persons  

def click_event(event, x, y, flags, params):
    global img_w
    global img_h
    # checking for left mouse clicks
    if event == cv2.EVENT_LBUTTONDOWN:
  
        # displaying the coordinates
        # on the Shell
        print(x, ' ', y)
        global point_coord
        point_coord = (x,y)
        print("Moving to " + str(point_coord))
        global img_w, img_h
