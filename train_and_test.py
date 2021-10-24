import matplotlib.pyplot as plt
from detecto.utils import read_image
from detecto.utils import xml_to_csv

from detecto.core import Dataset, Model
from detecto.visualize import show_labeled_image, plot_prediction_grid, detect_video, detect_live

DATA_ROOT = 'product-dataset/created/'


def main():
    xml_to_csv(DATA_ROOT, 'labels.csv')
    dataset = Dataset(DATA_ROOT)

    for image, targets in dataset:
        show_labeled_image(image, targets['boxes'], targets['labels'])

    # your_labels = ["818780014229", "071063437553", "818780014243", "078907420108"]
    # model = Model(your_labels)
    #
    # model.fit(dataset, verbose=True)
    #
    # # plot_prediction_grid(model, images, dim=(2, 2), figsize=(8, 8))
    # detect_video(model, 'admin_aifi12345@192.168.1.107_2020-04-20_08-02-57.mp4',
    #              'admin_aifi12345@192.168.1.107_2020-04-20_08-02-57-prediction.mp4')
    # detect_live(model, score_filter=0.7)  # Note: may not work on VMs


if __name__ == '__main__':
    main()
