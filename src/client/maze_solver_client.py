import os, sys, inspect
import cv2
import numpy as np
import argparse
import image_utils as utils
import time
from azure.storage.blob import BlockBlobService
from azure.storage.queue import QueueService

# Azure Blob Storage.
blob_account_name = 'btpstorage'
blob_account_key = 'Dt3XWm/Ozzv6boId/K6jpweTS/Bo5iVFKlARy9kjooRUGKede7s4W5plTKlUUSkO3SsrLekg7vHPtSlvm4QfSQ=='
block_blob_service = BlockBlobService(blob_account_name, blob_account_key)
container_name = 'btpcontainer'

# Azure Queue Storage
queue_account_name = 'btpqueue'
queue_account_key = 'mxP5vuDMAwrFVBwrbS+WkcmxH780PR/FfoxGKsW6DIPSnRhbshdhw43+b0Samda+9vrRUhz4R9MN4VLv1kN2KA=='
queue_service = QueueService(queue_account_name, queue_account_key)
queue_name = 'btpqueue'

use_local = True

# Pulls the image from azure blob storage.
def pull_image_from_blob(blob_name):
    blob = block_blob_service.get_blob_to_bytes(container_name, blob_name)

    # use numpy to construct an array from the bytes
    x = np.fromstring(blob.content, dtype='uint8')

    # decode the array into an image
    img = cv2.imdecode(x, cv2.IMREAD_UNCHANGED)
    return img

# Takes an image denoting a maze and solves the maze. returns the solved maze.
def solve_maze(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    thresholded_image = utils.adaptive_threshold(gray_image, cv2.THRESH_BINARY_INV)
    _, cnts, _ = cv2.findContours(thresholded_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(cnts) != 2:
        print(str(len(cnts)) + " Value Error Unable to solve maze - Failed at Contour finding!")

    solution_image = np.zeros(gray_image.shape, dtype=np.uint8)
    cv2.drawContours(solution_image, cnts, 0, (255,255,255),cv2.FILLED)

    kernel = np.ones((15, 15),  dtype=np.uint8)
    solution_image = cv2.dilate(solution_image, kernel)
    eroded_image = cv2.erode(solution_image, kernel)
    solution_image = cv2.absdiff(solution_image, eroded_image)

    b,g,r = cv2.split(image)
    b &= ~solution_image
    g |= solution_image
    r &= ~solution_image

    solution_image = cv2.merge([b,g,r]).astype(np.uint8)
    return solution_image

# uploads the image to azure blob storage.
def upload_to_blob(blob_name, image):
    # Create a file in Documents to test the upload and download.
    local_file_name = blob_name + ".jpg"
    cv2.imwrite(local_file_name, image)
    local_path=os.path.expanduser(".")
    full_path_to_file =os.path.join(local_path, local_file_name)

    # Logging
    print("Temp file = " + full_path_to_file)
    print("\nUploading to Blob storage as blob" + local_file_name)

    # Upload the created file if it doesn't exist, use local_file_name for the blob name.
    if not len(block_blob_service.list_blobs(container_name, local_file_name)):
        block_blob_service.create_blob_from_path(container_name, local_file_name, full_path_to_file)

# Loads the images from a folder.
def load_images_from_folder(folder):
    images = [[]]
    for filename in os.listdir(folder):
        img = cv2.imread(os.path.join(folder, filename))
        if img is not None:
            filename = os.path.splitext(filename)[0] # Remove extension.
            images.append([filename, img])
    return images

def solve():
    images_path = 'images/'
    images = load_images_from_folder(images_path)

    for image in images:
        if use_local:
            solution_image = solve_maze(image[1])
            cv2.imwrite("result_" + image[0] +".jpg", solution_image)
        else:
            print('uploading image: ' + image[0])
            upload_to_blob(image[0], image[1])
    
    if use_local:
        return

    print('Images uploaded successfully!')
    time.sleep(10*len(images))
    print('Downloading solved images from Azure Blob Storage!')
    for image in images:
        retry_count = 0
        while retry_count <= 10:
            if not len(block_blob_service.list_blobs(container_name, image[0] + '.jpg')):
                retry_count += 1
                time.sleep(10)
            else:
                solution_image_name = 'solution_' + image[0] + '.jpg'
                solution_image = pull_image_from_blob(solution_image_name)
                print('downloading solution image: ' + solution_image_name)
                cv2.imwrite(solution_image_name, solution_image)
                break

if __name__ == "__main__":
    solve()
    