import base64

import numpy as np
from pymongo import MongoClient
import cv2


def get_order_frames_per_camera_id(x, db):
    pipeline = [
        {"$match": {"camera_id": x}},
        {"$sort": {"document.header.t_origin": 1}},
    ]
    frame_message_collection = db["frame_message"]
    result = list(frame_message_collection.aggregate(pipeline))
    return x, result


def decode_frame(encoded_frame):
    nparr = np.frombuffer(base64.b64decode(encoded_frame), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return frame


def create_video_from_frames(test_name, i, frames):
    frames_data = list(
        map(
            lambda x: x["document"]["frame_message"]["frames"][0]["frame"]["data"],
            frames,
        )
    )
    decoded_frames = [decode_frame(encoded_frame) for encoded_frame in frames_data]
    height, width, _ = decoded_frames[0].shape
    out = cv2.VideoWriter(
        f"video_{test_name}_{i}.mp4",
        cv2.VideoWriter_fourcc(*"mp4v"),
        30.0,
        (width, height),
    )
    for frame in decoded_frames:
        out.write(frame)
    out.release()


if __name__ == "__main__":
    name = "cps-test-2"

    mongo_client = MongoClient("mongodb://localhost:27017")
    db = mongo_client[name]

    camera_ids = range(1, 11)
    frames_per_camera_in_order = list(
        map(
            lambda y: create_video_from_frames(name, y[0], y[1]),
            map(lambda x: get_order_frames_per_camera_id(x, db), camera_ids),
        )
    )
