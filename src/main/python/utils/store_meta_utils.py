def build_dicts_from_store_meta(gondolas_meta, shelves_meta, plates_meta):
    gondolas_dict = {}
    shelves_dict = {}
    plates_dict = {}

    for gondola_meta in gondolas_meta:
        gondolas_dict[str(gondola_meta["id"]["id"])] = gondola_meta

    for shelf_meta in shelves_meta:
        ids = shelf_meta["id"]
        gondola_id = ids["gondola_id"]["id"]
        shelf_id = ids["shelf_index"]
        shelf_meta_index_key = str(gondola_id) + "_" + str(shelf_id)
        shelves_dict[shelf_meta_index_key] = shelf_meta

    for plate_meta in plates_meta:
        ids = plate_meta["id"]
        gondola_id = ids["shelf_id"]["gondola_id"]["id"]
        shelf_id = ids["shelf_id"]["shelf_index"]
        plate_id = ids["plate_index"]
        plate_meta_index_key = (
            str(gondola_id) + "_" + str(shelf_id) + "_" + str(plate_id)
        )
        plates_dict[plate_meta_index_key] = plate_meta

    return gondolas_dict, shelves_dict, plates_dict
