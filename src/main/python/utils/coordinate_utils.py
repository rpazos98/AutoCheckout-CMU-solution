import numpy as np

from data.coordinates import Coordinates


def init_nd_array(*dims):
    # Initialize array with None values
    array = np.array([None] * np.prod(dims), dtype=object)
    array = array.reshape(dims)

    # Initialize each element of the array as an empty list
    def init_elements(arr, index, dims):
        if len(dims) == 1:
            for i in range(dims[0]):
                arr[i] = []
        else:
            for i in range(dims[index]):
                init_elements(arr[i], index + 1, dims[1:])

    init_elements(array, 0, dims)
    return array


def rolling_window(a, window):
    shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
    strides = a.strides + (a.strides[-1],)
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)


def get_3d_coordinates_for_plate(
    gondola, shelf, plate, gondolas_dict, shelves_dict, plates_dict
):
    gondola_meta_key = str(gondola)
    shelf_meta_key = str(gondola) + "_" + str(shelf)
    plate_meta_key = str(gondola) + "_" + str(shelf) + "_" + str(plate)

    # TODO: rotation values for one special gondola
    absolute_3d = Coordinates(0, 0, 0)
    gondola_translation = get_translation(gondolas_dict[gondola_meta_key])
    absolute_3d.translate_by(
        gondola_translation["x"], gondola_translation["y"], gondola_translation["z"]
    )

    if gondola == 5:
        # rotate by 90 degrees
        shelf_translation = get_translation(shelves_dict[shelf_meta_key])
        absolute_3d.translate_by(
            -shelf_translation["y"], shelf_translation["x"], shelf_translation["z"]
        )

        plate_translation = get_translation(plates_dict[plate_meta_key])
        absolute_3d.translate_by(
            -plate_translation["y"], plate_translation["x"], plate_translation["z"]
        )

    else:
        shelf_translation = get_translation(shelves_dict[shelf_meta_key])
        absolute_3d.translate_by(
            shelf_translation["x"], shelf_translation["y"], shelf_translation["z"]
        )

        key_ = plates_dict.get(plate_meta_key)
        if key_ is None:
            return absolute_3d
        plate_translation = get_translation(key_)
        absolute_3d.translate_by(
            plate_translation["x"], plate_translation["y"], plate_translation["z"]
        )

    return absolute_3d


def get_translation(meta):
    return meta["coordinates"]["transform"]["translation"]
