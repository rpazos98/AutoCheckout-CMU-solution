import os
import random
from pathlib import Path

from PIL import Image
from cv2 import cv2
from pascal_voc_writer import Writer

test_cases = ["BASELINE-8"]
SKU_EXAMPLE_MIN = 2


def generate_dataset():
    sku_to_png_list = get_sku_to_png_list()
    for test_case in test_cases:
        filtered_videos = get_candidate_videos_paths(test_case)
        for product_sku in sku_to_png_list.keys():
            sku_example_count = 0
            for filtered_video in filtered_videos:
                product_image_list = sku_to_png_list[product_sku]
                cap = cv2.VideoCapture(filtered_video)
                while sku_example_count < SKU_EXAMPLE_MIN:
                    ret, frame = cap.read()
                    if ret:
                        if random.choice([True, False]):
                            img2 = Image.open(random.choice(product_image_list))
                            save_path_combined_image = './product-dataset/created/{}-{}.png'.format(product_sku,
                                                                                                    sku_example_count)
                            parent_dir = save_path_combined_image.rsplit("/", 1)[0]
                            os.makedirs(parent_dir, exist_ok=True)
                            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            background = Image.fromarray(img)
                            x, y = random.randint(0, max(0, background.size[0] - img2.size[0])), \
                                   random.randint(0, max(0, background.size[1] - img2.size[1]))
                            background.paste(img2, (x, y), mask=img2)
                            background.save(save_path_combined_image)
                            writer = Writer(save_path_combined_image, 1266, 916)
                            xmin = x
                            xmax = x + img2.width
                            ymin = y
                            ymax = y + (img2.height)
                            writer.addObject(product_sku, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
                            writer.save('./product-dataset/created/{}-{}.xml'.format(product_sku,
                                                                                     sku_example_count))
                            sku_example_count = sku_example_count + 1
                    else:
                        cap = cv2.VideoCapture(filtered_video)
                cap.release()
                cv2.destroyAllWindows()


def get_candidate_videos_paths(test_case):
    targets__format = "videos/{}/targets/".format(test_case)
    path = Path(targets__format).resolve()
    all_videos = list_all_files_for_format(str(path), ".mp4")
    filtered_videos = list(filter(lambda x: '107' in x, all_videos))
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


if __name__ == '__main__':
    generate_dataset()
