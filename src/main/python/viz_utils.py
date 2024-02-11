import logging
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px

from Constants import NUM_GONDOLA, NUM_SHELF, NUM_PLATE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

GRAPH_ONLY_WITH_EVENTS = True
SHOULD_GRAPH = True
SHOULD_GRAPH_WEIGHT = False
SHOULD_GRAPH_SPATIAL_EVENTS = True


class VizUtils:
    def __init__(
        self,
        events,
        timestamps,
        db_name,
        weight_shelf_mean,
        weight_shelf_std,
        book_keeper,
    ):
        self.events = events
        self.timestamps = timestamps
        self.db_name = db_name
        self.weight_shelf_mean = weight_shelf_mean
        self.weight_shelf_std = weight_shelf_std
        self.event_to_position = {}
        self.event_to_product = {}
        self.book_keeper = book_keeper

    def graph(self):
        plates_coordinates = self.generate_get_plates_coordinates()
        if SHOULD_GRAPH:
            if SHOULD_GRAPH_WEIGHT:
                self.__graph_weight_shelf_data(
                    self.events,
                    self.weight_shelf_mean,
                    self.timestamps,
                    self.db_name,
                    "Weight Shelf Mean",
                )
                self.__graph_weight_shelf_data(
                    self.events,
                    self.weight_shelf_std,
                    self.timestamps,
                    self.db_name,
                    "Weight Shelf Standard",
                )
            if SHOULD_GRAPH_SPATIAL_EVENTS:
                self.__graph_plates(plates_coordinates, self.db_name, "Plates")
                self.__graph_event_to_position_3d(self.db_name, "Events")

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
                    if (
                        event.gondolaID - 1 == gondola_idx
                        and event.shelfID - 1 == shelf_idx
                    ):
                        had_events = True
                        plt.axvspan(
                            datetime.fromtimestamp(event.triggerBegin),
                            datetime.fromtimestamp(event.triggerEnd),
                            alpha=0.5,
                        )
                fig = plt.gcf()
                fig.autofmt_xdate()
                if had_events and GRAPH_ONLY_WITH_EVENTS:
                    plt.title(
                        "{} {} Gondola {} Shelf {}".format(
                            type, db_name, str(gondola_idx + 1), str(shelf_idx + 1)
                        )
                    )
                    plt.xlabel("Timestamp")
                    plt.ylabel("Weight in grams")
                    plt.plot(gondola_timestamps, y, color="green")
                    path_string = "results/{}/g{}/s{}/{}.png".format(
                        db_name, gondola_idx + 1, shelf_idx + 1, type
                    )
                    save_path = Path(path_string).resolve()
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    plt.savefig(str(save_path))
                    logging.info("Saving {}".format(path_string))
                plt.close()

    def graph_weight_plate_data(self, plate_data, timestamps, db_name, type):
        for gondola_idx, gondola in enumerate(plate_data):
            gondola_timestamps = timestamps[gondola_idx]
            f = lambda x: datetime.fromtimestamp(x)
            vfunc = np.vectorize(f)
            gondola_timestamps = vfunc(gondola_timestamps)
            for shelf_idx, shelf in enumerate(gondola):
                for plate_idx, plate in enumerate(shelf):
                    y = plate
                    plt.title(
                        "{} {} Gondola {} Shelf {} Plate {}".format(
                            type,
                            db_name,
                            str(gondola_idx + 1),
                            str(shelf_idx + 1),
                            str(plate_idx + 1),
                        )
                    )
                    plt.xlabel("Timestamp")
                    plt.ylabel("Weight in grams")
                    plt.plot(gondola_timestamps, y, color="green")
                    fig = plt.gcf()
                    fig.autofmt_xdate()
                    path_string = "results/{}/g{}/s{}/p{}/{}.png".format(
                        db_name, gondola_idx + 1, shelf_idx + 1, plate_idx + 1, type
                    )
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
        df = self.prepare_events_df()
        events = px.scatter_3d(
            df,
            x="x",
            y="y",
            z="z",
            color="timestamp_begin",
            size="weight_delta",
            symbol="event_type",
            hover_data=[
                "x",
                "z",
                "datetime_begin",
                "weight_delta",
                "event_type",
                "product_name",
                "product_quantity",
                "product_weight",
            ],
            range_x=[0, 4.5],
            range_y=[0, 2],
            range_z=[0, 2],
        )
        camera = dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=1.25, y=1.25, z=1.25),
        )
        path_string_html = "results/{}/{}.html".format(db_name, type)
        events.update_layout(
            scene_camera=camera, title=path_string_html, scene={"aspectmode": "cube"}
        )
        events.write_html(path_string_html)
        logging.info("Saving {}".format(path_string_html))

    def prepare_events_df(self):
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
            timestamp_begin.append(event.triggerBegin)
            weight_delta.append(abs(event.deltaWeight))
            event_type.append("TAKE" if event.deltaWeight < 0 else "LEAVE")
            product_name.append(product["name"])
            product_quantity.append(product["quantity"])
            product_weight.append(product["weight"])
        data = {
            "x": xs,
            "y": ys,
            "z": zs,
            "timestamp_begin": timestamp_begin,
            "weight_delta": weight_delta,
            "event_type": event_type,
            "product_name": product_name,
            "product_quantity": product_quantity,
            "product_weight": product_weight,
        }
        df = pd.DataFrame(data)
        df["datetime_begin"] = pd.to_datetime(df["timestamp_begin"], unit="s")
        return df

    def generate_get_plates_coordinates(self):
        xs = []
        zs = []
        ys = []
        tags = []
        gondolas = []
        shelves = []
        plates = []
        for gondola_id in range(1, NUM_GONDOLA):
            for shelf_id in range(1, NUM_SHELF):
                for plate_id in range(1, NUM_PLATE):
                    coordinates = self.book_keeper.get3DCoordinatesForPlate(
                        gondola_id, shelf_id, plate_id
                    )
                    xs.append(coordinates.x)
                    ys.append(coordinates.y)
                    zs.append(coordinates.z)
                    gondolas.append(gondola_id)
                    shelves.append(shelf_id)
                    plates.append(shelf_id)
                    tags.append(
                        "GONDOLA {}, SHELF {}, PLATE {}".format(
                            str(gondola_id), str(shelf_id), str(plate_id)
                        )
                    )
        data = {
            "x": xs,
            "y": ys,
            "z": zs,
            "tags": tags,
            "gondola": gondolas,
            "shelves": shelves,
            "plates": plates,
        }
        return pd.DataFrame(data)

    def __graph_plates(self, plates_coordinates, db_name, type):
        plotly_fig = px.scatter_3d(
            plates_coordinates,
            x="x",
            y="y",
            z="z",
            range_x=[0, 4.5],
            range_y=[0, 2],
            color="shelves",
            symbol="gondola",
            range_z=[0, 2],
            hover_data=["x", "y", "z", "gondola", "shelves", "plates"],
        )
        path_string_html = "results/{}/{}.html".format(db_name, type)
        plotly_fig.update_layout(title=path_string_html)
        plotly_fig.write_html(path_string_html)
        logging.info("Saving {}".format(path_string_html))
        return plotly_fig
