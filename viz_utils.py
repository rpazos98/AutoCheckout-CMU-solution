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

GRAPH_ONLY_WITH_EVENTS = True
SHOULD_GRAPH = True


class VizUtils:

    def __init__(self, events, timestamps, db_name, weight_shelf_mean, weight_shelf_std):
        self.events = events
        self.timestamps = timestamps
        self.db_name = db_name
        self.weight_shelf_mean = weight_shelf_mean
        self.weight_shelf_std = weight_shelf_std
        self.event_to_position = {}

    def graph(self):
        if SHOULD_GRAPH:
            self.__graph_weight_shelf_data(self.events, self.weight_shelf_mean, self.timestamps, self.db_name,
                                           "Weight Shelf Mean")
            self.__graph_weight_shelf_data(self.events, self.weight_shelf_std, self.timestamps, self.db_name,
                                           "Weight Shelf Standard")
            self.__graph_event_to_position_3d(self.event_to_position, self.db_name, "Events in space")

    def __graph_weight_shelf_data(self, events, shelf_data, timestamps, db_name, type):
        for gondola_idx, gondola in enumerate(shelf_data):
            gondola_timestamps = timestamps[gondola_idx]
            f = lambda x: datetime.fromtimestamp(x)
            vfunc = np.vectorize(f)
            gondola_timestamps = vfunc(gondola_timestamps)
            for shelf_idx, shelf in enumerate(gondola):
                had_events = False
                y = shelf
                plt.title("{} {} Gondola {} Shelf {}".format(type, db_name, str(gondola_idx), str(shelf_idx)))
                plt.xlabel("Timestamp")
                plt.ylabel("Weight in grams")
                plt.plot(gondola_timestamps, y, color="green")
                for event in events:
                    if event.gondolaID - 1 == gondola_idx and event.shelfID - 1 == shelf_idx:
                        had_events = True
                        plt.axvspan(datetime.fromtimestamp(event.triggerBegin),
                                    datetime.fromtimestamp(event.triggerEnd),
                                    alpha=0.5)
                fig = plt.gcf()
                fig.autofmt_xdate()
                if had_events and GRAPH_ONLY_WITH_EVENTS:
                    path_string = "results/{}/g{}/s{}/{}.png".format(db_name, gondola_idx, shelf_idx, type)
                    save_path = Path(path_string).resolve()
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    plt.savefig(str(save_path))
                    logging.info("Saving {}".format(path_string))
                plt.close()

    def graph_weight_plate_data(self, events, plate_data, timestamps, db_name, type):
        for gondola_idx, gondola in enumerate(plate_data):
            gondola_timestamps = timestamps[gondola_idx]
            f = lambda x: datetime.fromtimestamp(x)
            vfunc = np.vectorize(f)
            gondola_timestamps = vfunc(gondola_timestamps)
            for shelf_idx, shelf in enumerate(gondola):
                for plate_idx, plate in enumerate(shelf):
                    y = plate
                    plt.title(
                        "{} {} Gondola {} Shelf {} Plate {}".format(type, db_name, str(gondola_idx), str(shelf_idx),
                                                                    str(plate_idx)))
                    plt.xlabel("Timestamp")
                    plt.ylabel("Weight in grams")
                    plt.plot(gondola_timestamps, y, color="green")
                    fig = plt.gcf()
                    fig.autofmt_xdate()
                    path_string = "results/{}/g{}/s{}/p{}/{}.png".format(db_name, gondola_idx, shelf_idx, plate_idx,
                                                                         type)
                    save_path = Path(path_string).resolve()
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    plt.savefig(str(save_path))
                    logging.info("Saving {}".format(path_string))
                    plt.close()

    def addEventPosition(self, event, absolute_pos):
        self.event_to_position[event] = absolute_pos

    def __graph_event_to_position_3d(self, event_to_position, db_name, type):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        for event, position in event_to_position.items():
            ax.scatter(position.x, position.y, position.z)
            ax.text(position.x, position.y, position.z, '%s' % (str(datetime.fromtimestamp(event.triggerBegin).time())),
                    size=10, zorder=1,
                    color='k')
        path_string = "results/{}/{}.png".format(db_name, type)
        save_path = Path(path_string).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(save_path))
