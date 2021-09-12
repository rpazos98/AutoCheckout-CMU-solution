from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)


def graph_weight_shelf_data(events, shelf_data, timestamps, db_name, type):
    for gondola_idx, gondola in enumerate(shelf_data):
        gondola_timestamps = timestamps[gondola_idx]
        f = lambda x: datetime.fromtimestamp(x)
        vfunc = np.vectorize(f)
        gondola_timestamps = vfunc(gondola_timestamps)
        for shelf_idx, shelf in enumerate(gondola):
            y = shelf
            plt.title("{} {} Gondola {} Shelf {}".format(type, db_name, str(gondola_idx), str(shelf_idx)))
            plt.xlabel("Timestamp")
            plt.ylabel("Weight in grams")
            plt.plot(gondola_timestamps, y, color="green")
            for event in events:
                if event.gondolaID - 1 == gondola_idx and event.shelfID - 1 == shelf_idx:
                    plt.axvspan(datetime.fromtimestamp(event.triggerBegin), datetime.fromtimestamp(event.triggerEnd),
                                alpha=0.5)
            fig = plt.gcf()
            fig.autofmt_xdate()
            path_string = "results/{}/g{}/s{}/{}.png".format(db_name, gondola_idx, shelf_idx, type)
            save_path = Path(path_string).resolve()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(str(save_path))
            logging.info("Saving {}".format(path_string))
            plt.close()


def graph_weight_plate_data(events, plate_data, timestamps, db_name, type):
    for gondola_idx, gondola in enumerate(plate_data):
        gondola_timestamps = timestamps[gondola_idx]
        f = lambda x: datetime.fromtimestamp(x)
        vfunc = np.vectorize(f)
        gondola_timestamps = vfunc(gondola_timestamps)
        for shelf_idx, shelf in enumerate(gondola):
            for plate_idx, plate in enumerate(shelf):
                y = plate
                plt.title("{} {} Gondola {} Shelf {} Plate {}".format(type, db_name, str(gondola_idx), str(shelf_idx),
                                                                      str(plate_idx)))
                plt.xlabel("Timestamp")
                plt.ylabel("Weight in grams")
                plt.plot(gondola_timestamps, y, color="green")
                fig = plt.gcf()
                fig.autofmt_xdate()
                path_string = "results/{}/g{}/s{}/p{}/{}.png".format(db_name, gondola_idx, shelf_idx, plate_idx, type)
                save_path = Path(path_string).resolve()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                plt.savefig(str(save_path))
                logging.info("Saving {}".format(path_string))
                plt.close()
