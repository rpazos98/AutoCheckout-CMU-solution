import json
import os
import subprocess
import zipfile
from datetime import datetime

import requests
import tqdm

# GET test cases
headers = {"TOKEN": "5ea023be-b530-4816-8eda-5340cfabe9b0"}
response = requests.get(
    url="http://cps-week.internal.aifi.io/api/v1/testcases", headers=headers
)

testCases = []
if response.status_code == 200:
    responsStr = response.content
    testCases = json.loads(responsStr)
    with open("../../../../doc/competition/test_cases.json", "w") as f:
        json.dump(testCases, f)


# with open("competition/test_cases_specific.json", 'r') as f:
#     testCases = json.load(f)


def mkdir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)


videosDir = "./videos/"
mkdir(videosDir)

archivesDir = "./archives/"
mkdir(archivesDir)

imagesDir = "./product-dataset/images"
mkdir(imagesDir)

testCaseJSONFilePath = "./competition/TestCaseStartTime.json"
testCaseStartTime = {}
if os.path.exists(testCaseJSONFilePath):
    with open(testCaseJSONFilePath) as f:
        testCaseStartTime = json.load(f)


def get_dataset():
    for testCase in testCases:
        archives = testCase["archives"]
        name = testCase["name"]
        if True:
            videos = testCase["videos"]
            dirForCurrentTestCase = videosDir + name
            if os.path.exists(dirForCurrentTestCase):
                print("have videos already, ", dirForCurrentTestCase)
            else:
                for url in videos:
                    if url.endswith("Videos.zip"):
                        newUrl = url.replace("cloud.google", "googleapis")
                        print(newUrl)
                        r = requests.get(newUrl)
                        zipPath = videosDir + "Videos.zip"
                        open(zipPath, "wb").write(r.content)
                        with zipfile.ZipFile(zipPath, "r") as zip_ref:
                            zip_ref.extractall(videosDir)
                        os.unlink(zipPath)
            timestamps = []
            for videoName in os.listdir(dirForCurrentTestCase):
                # print(videoName)
                split1 = videoName.split("_")
                dateStr, fooTimeStr = split1[1], split1[2]
                timeStr = fooTimeStr.split(".")[0]
                completeTimeStr = dateStr + "_" + timeStr
                if name in ["BASELINE-1", "BASELINE-2", "BASELINE-3", "BASELINE-4"]:
                    print("special! ", name)
                    completeTimeStr += " +0200"
                else:
                    completeTimeStr += " +0000"
                # '2020-04-20_07-33-37'
                datetimeObj = datetime.strptime(completeTimeStr, "%Y-%m-%d_%H-%M-%S %z")
                timestamps.append(datetimeObj.timestamp())
            timestamps.sort()
            testCaseStartTime[name] = timestamps[0]
            print(testCaseStartTime)

        archivePath = archivesDir + name + ".archive"
        if os.path.exists(archivePath):
            print("already have archive ", archivePath)
        else:
            for url in archives:
                if url.endswith(".archive"):
                    newUrl = url.replace("cloud.google", "googleapis")
                    print(newUrl)
                    r = requests.get(newUrl)
                    open(archivePath, "wb").write(r.content)
                    dbRestoreCommand = "mongorestore --archive=" + archivePath
                    proc = subprocess.Popen(
                        [dbRestoreCommand], stdout=subprocess.PIPE, shell=True
                    )
                    (out, err) = proc.communicate()

    with open(testCaseJSONFilePath, "w") as f:
        json.dump(testCaseStartTime, f)


def get_product_image_dataset():
    # load links into a list
    links = []
    with open("../../../../doc/competition/product-dataset-reduced.txt") as f:
        links = f.readlines()
    # download the zip
    for link in tqdm.tqdm(links, desc="Zip downloading"):
        filename = link.rsplit("/", 1)[-1]
        filename = filename.rstrip()
        link = link.rstrip()
        zip_dir = "./product-dataset/zips/{}".format(filename)
        print("Downloading {}".format(filename))
        if not os.path.isfile(zip_dir):
            newUrl = link.replace("cloud.google", "googleapis")
            print(newUrl)
            r = requests.get(newUrl)
            open(zip_dir, "wb").write(r.content)
            with zipfile.ZipFile(zip_dir, "r") as zip_ref:
                zip_ref.extractall(imagesDir)
            os.unlink(zip_dir)
    # uncompress the zip into a specific folder and remove the zip
    zips = os.listdir("./product-dataset/zips")
    for zip in tqdm.tqdm(zips, desc="Unzipping product zips"):
        zip_file = "./product-dataset/zips/{}".format(zip)
        print("Decompressing {}".format(zip_file))
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall("./product-dataset/images/{}".format(zip.rsplit(".")[0]))


if __name__ == "__main__":
    # get_dataset()
    get_product_image_dataset()
