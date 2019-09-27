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

while(True):
    # Get the messages from the queue.
    messages = queue_service.get_messages(queue_name, num_messages=5, visibility_timeout=5*60)
    for message in messages:
        blob_name = message.content
        print('Solving the maze with name ' + blob_name)
        image_binary = pull_image_from_blob(blob_name)
        solved_image = solve_maze(image_binary)
        if solved_image is not None:
            upload_to_blob(blob_name, solved_image)
        queue_service.delete_message(queue_name, message.id, message.pop_receipt)
    
    # Sleep for 10 seconds.
    time.sleep(10)

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
    try:
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        thresholded_image = utils.adaptive_threshold(
            gray_image, cv2.THRESH_BINARY_INV)
        print('Finding Contours')
        contours, _ = cv2.findContours(
            thresholded_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        solution_image = np.zeros(gray_image.shape, dtype=np.uint8)
        cv2.drawContours(solution_image, contours, 0, (255, 255, 255), 5)

        print('Dilation')
        kernel = np.ones((15, 15),  dtype=np.uint8)
        solution_image = cv2.dilate(solution_image, kernel)
        eroded_image = cv2.erode(solution_image, kernel)
        solution_image = cv2.absdiff(solution_image, eroded_image)

        b, g, r = cv2.split(image)
        b &= ~solution_image
        g |= solution_image
        r &= ~solution_image

        print('Merging to get the final solution')
        solution_image = cv2.merge([b, g, r]).astype(np.uint8)
        return solution_image
    except Exception:
        return None

def exists(local_file_name):
    return block_blob_service.exists(container_name, local_file_name)

# uploads the solution image to azure blob storage.
def upload_to_blob(blob_name, solution_image):
    # Create a file in Documents to test the upload and download.
    local_file_name = "result_" + blob_name
    cv2.imwrite(local_file_name, solution_image)
    local_path=os.path.expanduser(".")
    full_path_to_file =os.path.join(local_path, local_file_name)

    # Logging
    print("Temp file = " + full_path_to_file)
    print("\nUploading to Blob storage as blob" + local_file_name)

    # Upload the created file if it doesn't exist, use local_file_name for the blob name.
    if not exists(local_file_name):
        block_blob_service.create_blob_from_path(container_name, local_file_name, full_path_to_file)
    
    # Delete the temporary solution image after upload
    os.remove(full_path_to_file)
