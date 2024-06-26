# Code for Evaluation
import json

from cashier import process
from constants import DEBUG, VERBOSE

"""
Groundtruth file contains pickup event and putback event separately.
remove_putback_products() will remove the putback event as well as its corresponding pickup event,
so that the ground truth only contains file result. 
"""


def remove_putback_products(gt_list):
    for db in gt_list:
        final_events = []
        for event in db["events"]:
            if event["putback"] == 0:  # pick up
                final_events.append(event)
            else:  # putback => remove from final_events the coresponding pickup event
                for i in range(len(final_events)):
                    final_event = final_events[i]
                    if (
                        final_event["observation"]["target_id"]
                        != event["observation"]["target_id"]
                    ):
                        continue
                    if (
                        final_event["observation"]["products"][0]["id"]
                        != event["observation"]["products"][0]["id"]
                    ):
                        continue
                    del final_events[i]
                    break
        db["events"] = final_events


"""
1. Evaluate inventory status
Metrics:
    1. Precision: TP/(TP+FP)
    2. Recall: TP/(TP+FN)
2. Evaluate association accuracy
Metrics:
    1. Accuracy: num_correct_association/num_correct_products
"""


def evaluate_inventory(dbs, gt_path):
    # Load JSON groundtruth
    with open(gt_path) as f:
        gt_data = json.load(f)

    gt_list = gt_data["lists"]
    if not DEBUG:
        remove_putback_products(gt_list)
        # with open('gt_final.json', 'w') as outfile:
        #     json.dump(gt_data, outfile)

    # Metrics
    tp, fp, tn, fn = 0, 0, 0, 0
    overall_num_preds, overall_num_gt = 0, 0
    for i in range(len(dbs)):
        print("\n\nEvaluating database: ", dbs[i])
        # Metrics per database
        db_tp, db_fp, db_tn, db_fn = 0, 0, 0, 0
        db_pred_counts, db_gt_counts = 0, 0

        ########## Generate Prediction ##########
        db_name = dbs[i]
        receipts = process(db_name)

        ########## Evaluate Ground truth ##########
        gt_entry = gt_list[i]
        # Find groundtruth entry for this database
        tmp_i = 0
        while gt_entry["dataset"] != db_name:
            tmp_i += 1
            gt_entry = gt_list[tmp_i]
            assert tmp_i < len(gt_list)
        assert gt_entry["dataset"] == db_name
        event_list = gt_entry["events"]
        for event in event_list:
            gt_products = event["observation"]["products"]
            gt_customerID = event["observation"]["target_id"]
            # Find the corresponding customer receipts
            if gt_customerID in receipts:
                # Find the corresponding products on the receipt
                customer_receipt = receipts[gt_customerID]
                for gt_product in gt_products:
                    gt_productID = gt_product["id"]
                    for productID, entry in customer_receipt.purchaseList.items():
                        if gt_productID == productID:
                            product, quantity = entry
                            if quantity > 0:
                                db_tp += 1
                                customer_receipt.purchaseList[productID] = (
                                    product,
                                    quantity - 1,
                                )  # entry = (product, quantity)
                    db_gt_counts += 1
            else:
                # No such customer
                for gt_product in gt_products:
                    db_gt_counts += 1

        # Print False Items

        num_receipt = 0
        for id, customer_receipt in receipts.items():
            if VERBOSE:
                print(
                    "============== False Receipt {} ==============".format(num_receipt)
                )
                print("Customer ID: " + id)
                print("Purchase List: ")
            for _, entry in customer_receipt.purchaseList.items():
                product, quantity = entry
                if quantity != 0:
                    if VERBOSE:
                        print(
                            "*Name: " + product.name + ", Quantities: " + str(quantity),
                            product.thumbnail,
                        )
                    db_fp += quantity
            num_receipt += 1

        db_fn = db_gt_counts - db_tp
        db_pred_counts = db_tp + db_fp
        overall_num_preds += db_pred_counts
        overall_num_gt += db_gt_counts
        tp += db_tp
        fp += db_fp
        fn += db_fn

        # Display DB Evaluation
        print(
            "Database: {}, Correct Items on Receipts: {}/{}, Total GT items: {}".format(
                db_name, db_tp, db_pred_counts, db_gt_counts
            )
        )

    print("\n================== Evaluation Summary ==================")
    print("Databases: ", dbs)
    print("Ground truth version: ", gt_path)
    precision = 0.0 if tp + fp == 0 else tp * 100.0 / (tp + fp)
    print("Overall precision is: {:.1f}%".format(precision))
    recall = 0.0 if tp + fn == 0 else tp * 100.0 / (tp + fn)
    print("Overall recall is: {:.1f}%".format(recall))
    if precision + recall == 0:
        f1 = 0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    print("Overall F1 is: {:.1f}%".format(f1))


if __name__ == "__main__":
    # dbs =['cps-test-01', 'cps-test-2'] + ['cps-test-'+str(i) for i in range(4, 13)]
    dbs = ["cps-test-2"]
    # dbs += ['cps-test-19', 'cps-test-20','cps-test-21','cps-test-22','cps-test-23','cps-test-24'] # TODO: cps-test-23 exception
    # dbs += ['ALL-SIMPLE-CHIP-1', 'TEAM-PEI-1', 'TEAM-PEI-JD-1', 'TEAM-8-1']
    # dbs = ['BASELINE-1','BASELINE-2','BASELINE-3', 'BASELINE-4', 'BASELINE-5', 'BASELINE-6', 'BASELINE-7','BASELINE-8','BASELINE-10','BASELINE-11', 'BASELINE-12', 'BASELINE-13', 'BASELINE-14', 'BASELINE-16', 'BASELINE-20', 'BASELINE-22', 'BASELINE-23', 'BASELINE-25']
    gt_path = "src/main/resources/ground_truth/v14.json"  # list of ground truth W.R.T the previous databases
    evaluate_inventory(dbs, gt_path)
