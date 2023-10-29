import os

from detecto.core import Dataset, Model, DataLoader
from detecto.utils import read_image
from detecto.visualize import (
    show_labeled_image,
    plot_prediction_grid,
    detect_video,
    detect_live,
)
from matplotlib import pyplot as plt

TRAIN_ROOT = "product-dataset/created/train"
TEST_ROOT = "product-dataset/created/test"
MODEL_PATH = "model_weights.pth"
LABELS = [
    "818780014229",
    "071063437553",
    "818780014243",
    "078907420108",
    "012000028458",
]


def main():
    train = Dataset(TRAIN_ROOT)
    test = Dataset(TEST_ROOT)

    train = DataLoader(train, batch_size=10, shuffle=True)

    for image, targets in test:
        show_labeled_image(image, targets["boxes"], targets["labels"])

    if not os.path.isfile(MODEL_PATH):
        model = Model(LABELS)
        losses = model.fit(train, val_dataset=test, verbose=True, epochs=5)
        model.save(MODEL_PATH)
        plt.plot(losses)
        plt.show()
    else:
        model = Model.load(MODEL_PATH, LABELS)

    image = read_image("product-dataset/created/test/012000028458-0.png")
    labels, boxes, scores = model.predict_top(image)
    show_labeled_image(image, boxes, labels)


if __name__ == "__main__":
    main()
