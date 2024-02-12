import json
import os


def get_test_start_time(plate_cursor, dbname):
    video_start_time = get_clean_start_time(dbname)
    db_start_time = plate_cursor.find_one(sort=[("timestamp", 1)])["timestamp"]
    if video_start_time - db_start_time >= 10:
        return video_start_time
    else:
        return 0


def get_clean_start_time(dbname):
    test_case_start_time_json_file_path = "src/main/resources/TestCaseStartTime.json"
    if os.path.exists(test_case_start_time_json_file_path):
        with open(test_case_start_time_json_file_path, "r") as f:
            test_start_time = json.load(f)
        if dbname not in test_start_time:
            return 0
        return test_start_time[dbname]
    else:
        print(
            "!!!WARNING: Didn't find competition/TestCaseStartTime.json, results might not be accurate. "
            "Please run time_travel.py to get the json file"
        )
        return 0
