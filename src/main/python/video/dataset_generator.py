import os
import random
import shutil
from pathlib import Path

import albumentations as A
import numpy as np
from PIL import Image
from cv2 import cv2
from pascal_voc_writer import Writer

test_cases = ["BASELINE-8"]
SKU_EXAMPLE_MIN = 1000
FRAMES_PER_VIDEO = 10000
XML = "./product-dataset/created/{}-{}.xml"
JPG = "./product-dataset/created/{}-{}.jpg"

transform = A.Compose(
    [
        A.RandomBrightnessContrast(brightness_limit=(-0.4, 0.4), p=0.7),
    ]
)


def generate_dataset():
    generated_files = []
    frames = []
    for test_case in test_cases:
        filtered_videos = get_candidate_videos_paths(test_case)
        for filtered_video in filtered_videos:
            frame_per_video = 0
            cap = cv2.VideoCapture(filtered_video)
            ret, frame = cap.read()
            while ret and frame_per_video < FRAMES_PER_VIDEO:
                if random.choice([True, False, False]):
                    cropped_frame = frame[0:900, 366:1266]
                    frames.append(cropped_frame)
                    frame_per_video += 1
            cap.release()
    sku_to_png_list = get_sku_to_png_list()
    for product_sku in sku_to_png_list.keys():
        sku_example_count = 0
        product_image_list = sku_to_png_list[product_sku]
        while sku_example_count < SKU_EXAMPLE_MIN:
            if random.choice([True, False]):
                product = Image.open(random.choice(product_image_list))
                transformed_product = transform(image=np.array(product))["image"]
                transformed_product = Image.fromarray(
                    np.uint8(transformed_product)
                ).convert("RGB")
                image_path = JPG.format(product_sku, sku_example_count)
                parent_dir = image_path.rsplit("/", 1)[0]
                os.makedirs(parent_dir, exist_ok=True)
                img = cv2.cvtColor(random.choice(frames), cv2.COLOR_BGR2RGB)
                background = Image.fromarray(img)
                x, y = random.randint(
                    0, max(0, background.size[0] - product.size[0])
                ), random.randint(0, max(0, background.size[1] - product.size[1]))
                background.paste(transformed_product, (x, y), mask=product)
                background.thumbnail((300, 300), Image.ANTIALIAS)
                background.save(image_path)
                writer = Writer(image_path, 300, 300)
                xmin = x
                xmax = x + product.width
                ymin = y
                ymax = y + product.height
                writer.addObject(
                    product_sku,
                    xmin=xmin / 3,
                    ymin=ymin / 3,
                    xmax=xmax / 3,
                    ymax=ymax / 3,
                )
                xml_path = XML.format(product_sku, sku_example_count)
                writer.save(xml_path)
                sku_example_count += 1
                generated_files.append((image_path, xml_path))
                # for i in range(5):
                #     transformed_image = transform(image=np.array(background))['image']
                #     transformed_image = Image.fromarray(np.uint8(transformed_image)).convert('RGB')
                #     xml_transformed_path = XML.format(product_sku, sku_example_count)
                #     writer.save(xml_transformed_path)
                #     jpg_transformed_path = JPG.format(product_sku, sku_example_count)
                #     transformed_image.save(jpg_transformed_path)
                #     generated_files.append((jpg_transformed_path, xml_transformed_path))
                #     sku_example_count += 1
    random.shuffle(generated_files)
    create_train_and_test(generated_files, 0.7)


def create_train_and_test(generated_files, train_size):
    train_list = generated_files[0 : int(len(generated_files) * train_size)]
    test_list = generated_files[
        int(len(generated_files) * train_size) : int(len(generated_files))
    ]
    for train in train_list:
        dir_name = "train"
        os.makedirs("product-dataset/created/{}".format(dir_name), exist_ok=True)
        move_file(dir_name, train)
    for test in test_list:
        dir_name = "test"
        os.makedirs("product-dataset/created/{}".format(dir_name), exist_ok=True)
        move_file(dir_name, test)


def move_file(dir_name, test):
    image, xml = test
    image_filename = image.split("/")[-1]
    xml_filename = xml.split("/")[-1]
    image_destination = "product-dataset/created/{}/{}".format(dir_name, image_filename)
    xml_destination = "product-dataset/created/{}/{}".format(dir_name, xml_filename)
    shutil.move(image, image_destination, copy_function=shutil.copy2)
    shutil.move(xml, xml_destination, copy_function=shutil.copy2)


def get_candidate_videos_paths(test_case):
    targets__format = "videos/{}/targets/".format(test_case)
    path = Path(targets__format).resolve()
    all_videos = list_all_files_for_format(str(path), ".mp4")
    filtered_videos = list(filter(lambda x: "107" in x, all_videos))
    filtered_videos = list(filter(lambda x: not "predictions" in x, filtered_videos))
    return filtered_videos


def get_sku_to_png_list():
    result = {}
    targets__format = "product-dataset/images/"
    path = Path(targets__format).resolve()
    skus = os.listdir(str(path))
    for sku in skus:
        sku_path = os.path.join(str(path), sku)
        all_images = list_all_files_for_format(str(sku_path), ".png")
        result[sku] = all_images
    return result


def list_all_files_for_format(path, format):
    files = []
    # r=root, d=directories, f = files
    for r, d, f in os.walk(path):
        for file in f:
            if format in file:
                files.append(os.path.join(r, file))
    return files


if __name__ == "__main__":
    generate_dataset()
