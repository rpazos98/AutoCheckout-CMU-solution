# Autocheckout update

This project is based on the [winning solution](https://github.com/AutoCheckout-CMU/AutoCheckout) from the competition created by AiFi. The intent is to 

- improve the code structure
- incorporate better engineering tools and practices
- investigate and propose a solution based on computer vision

## Description

This project is being developed in the context of the graduation project of the 
[AI Specialization](https://lse.posgrados.fi.uba.ar/posgrados/especializaciones/inteligencia-artificial) offered by the 
University of Buenos Aires.

It is based on a prior solution to the problem, and it aims to solve the scenarios that the original solution was not 
able to solve (see [results evaluation](doc/evaluation.md)).

At the same time there is a lot of effort in improving the code and engineering practices and tooling. The objective is 
to make the project easy to execute and replicate

## Getting started

Follow these steps to run the project locally.

### Pre-requisites

#### Data Download

Download files from the [competition repo](https://github.com/JoaoDiogoFalcao/AutoCheckout/blob/master/README.md). 
Save as many as you want in `data/downloads`

#### docker-compose

Get the docker-compose images running, using `docker-compose up -d`

#### Mongo Compass (optional)

[Install](https://www.mongodb.com/try/download/compass) the UI tooling to monitor the data being properly restored in 
your db.

Connect to the database that was brought up in the last step using `mongodb://localhost:27017` as connection string

#### Install mongo tooling

Find [here](https://www.mongodb.com/try/download/database-tools) the version for your machine. This set of tools
contains mongorestore, which will be used in the next step

#### Use mongorestore

Execute this command, changing the archive name as corresponding

`mongorestore --archive=./data/downloads/<db-name>.archive --host localhost --port 27017`

#### Prepare Env

First you need to have [Conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html) installed.

Then you must execute `conda env create -f environment.yml` to replicate the `AutoCheckout` environment locally.

To activate the environment you need to execute `conda activate AutoCheckout`

After that you should execute `pip install -r requirementst.txt` to make sure all dependencies are installed.

## Executing the program

The entry point to the program is the `evalution.py` script. After the execution a report will appear in the terminal
showing relevant information of the execution

```
Evaluating database:  cps-test-2
Capture 3 events in the database cps-test-2
==============================================================
Predicted: [084114115881][putback=0] Kettle Chips Jalapeno, weight=62g, count=1
Predicted: [042238722149][putback=0] Haribo Starmix, weight=148g, count=1
Predicted: [632565000029][putback=0] FIJI NATURAL WATER 1LTR, weight=1059g, count=1
Database: cps-test-2, Correct Items on Receipts: 2/3, Total GT items: 3

================== Evaluation Summary ==================
Databases:  ['cps-test-2']
Ground truth version:  ground_truth/v14.json
Overall precision is: 66.7%
Overall recall is: 66.7%
Overall F1 is: 66.7%
```

## Housekeeping

### Formatter

For this project we are using the Black formatter.

To format your code with it just type in `black .`. This will apply the format to all the code

If the code does not comply with black the pre-commit hooks will fail.

### Execution validation

In order to make sure that we are always pushing working code we are executing `evalution.py` in the pre-commit hook.
This is the only validation loop today. As we improve this with tests we will be adding those to the hook.