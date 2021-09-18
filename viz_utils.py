from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px

import pandas as pd

import logging

from GroundTruthHelper import Product

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

GRAPH_ONLY_WITH_EVENTS = True
SHOULD_GRAPH = True
SHOULD_GRAPH_WEIGHT = False
SHOULD_GRAPH_SPATIAL_EVENTS = True


class VizUtils:

    def __init__(self, events, timestamps, db_name, weight_shelf_mean, weight_shelf_std):
        self.events = events
        self.timestamps = timestamps
        self.db_name = db_name
        self.weight_shelf_mean = weight_shelf_mean
        self.weight_shelf_std = weight_shelf_std
        self.event_to_position = {}
        self.event_to_product = {}

    def graph(self):
        if SHOULD_GRAPH:
            if SHOULD_GRAPH_WEIGHT:
                self.__graph_weight_shelf_data(self.events, self.weight_shelf_mean, self.timestamps, self.db_name,
                                               "Weight Shelf Mean")
                self.__graph_weight_shelf_data(self.events, self.weight_shelf_std, self.timestamps, self.db_name,
                                               "Weight Shelf Standard")
            if SHOULD_GRAPH_SPATIAL_EVENTS:
                self.__graph_event_to_position_3d(self.db_name, "Events in space")

    def __graph_weight_shelf_data(self, events, shelf_data, timestamps, db_name, type):
        for gondola_idx, gondola in enumerate(shelf_data):
            gondola_timestamps = timestamps[gondola_idx]
            f = lambda x: datetime.fromtimestamp(x)
            vfunc = np.vectorize(f)
            gondola_timestamps = vfunc(gondola_timestamps)
            for shelf_idx, shelf in enumerate(gondola):
                had_events = False
                y = shelf
                for event in events:
                    if event.gondolaID - 1 == gondola_idx and event.shelfID - 1 == shelf_idx:
                        had_events = True
                        plt.axvspan(datetime.fromtimestamp(event.triggerBegin),
                                    datetime.fromtimestamp(event.triggerEnd),
                                    alpha=0.5)
                fig = plt.gcf()
                fig.autofmt_xdate()
                if had_events and GRAPH_ONLY_WITH_EVENTS:
                    plt.title("{} {} Gondola {} Shelf {}".format(type, db_name, str(gondola_idx), str(shelf_idx)))
                    plt.xlabel("Timestamp")
                    plt.ylabel("Weight in grams")
                    plt.plot(gondola_timestamps, y, color="green")
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

    def addEventProduct(self, event, product):
        if product is not None:
            self.event_to_product[event] = product

    def __graph_event_to_position_3d(self, db_name, type):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        xs = []
        ys = []
        zs = []
        timestamp_begin = []
        weight_delta = []
        event_type = []
        product_name = []
        product_quantity = []
        product_weight = []
        for event, product in self.event_to_product.items():
            position = self.event_to_position.get(event)
            xs.append(position.x)
            ys.append(position.y)
            zs.append(position.z)
            # timestamp_begin.append(datetime.fromtimestamp(event.triggerBegin))
            timestamp_begin.append(event.triggerBegin)
            weight_delta.append(abs(event.deltaWeight))
            event_type.append("TAKE" if event.deltaWeight < 0 else "LEAVE")
            product_name.append(product["name"])
            product_quantity.append(product["quantity"])
            product_weight.append(product["weight"])
            ax.scatter(position.x, position.y, position.z)
            tag = 'T: {} \n ΔW: {:.1f} \n ({:.3f}, {:.3f}, {:.3f})'.format(
                str(datetime.fromtimestamp(event.triggerBegin).time()), event.deltaWeight, position.x, position.y,
                position.z)
            ax.text(position.x, position.y, position.z,
                    tag,
                    size=5, zorder=1,
                    color='k')
        data = {"x": xs, "y": ys, "z": zs, "timestamp_begin": timestamp_begin, "weight_delta": weight_delta,
                "event_type": event_type, "product_name": product_name, "product_quantity": product_quantity,
                "product_weight": product_weight}
        df = pd.DataFrame(data)
        df["datetime_begin"] = pd.to_datetime(df["timestamp_begin"], unit='s')
        # plotly_fig = px.scatter_3d(df, x='x', y='y', z='z',
        #                            color='timestamp_begin', size='weight_delta', symbol="event_type")
        plotly_fig = px.scatter(df, x='x', y='z',
                                color='datetime_begin', size='weight_delta', symbol="event_type",
                                hover_data=['x', 'z', 'datetime_begin', 'weight_delta', "event_type", "product_name",
                                            "product_quantity", "product_weight"])
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')
        path_string_png = "results/{}/{}.png".format(db_name, type)
        path_string_html = "results/{}/{}.html".format(db_name, type)
        save_path = Path(path_string_png).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(save_path))
        logging.info("Saving {}".format(path_string_png))
        camera = dict(
            up=dict(x=0, y=1, z=0),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=1.25, y=1.25, z=1.25)
        )
        plotly_fig.update_layout(scene_camera=camera, title=path_string_html)
        plotly_fig.update_xaxes(range=[0, 4.5])
        plotly_fig.update_yaxes(range=[0, 2])
        plotly_fig.write_html(path_string_html)
        logging.info("Saving {}".format(path_string_html))
