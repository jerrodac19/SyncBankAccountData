# main.py
import time
import subprocess
import os
import random
import re
import sys
from collections import Counter
from typing import List
from datetime import datetime

from data_retrievers import BrowserDataRetriever, ApiDataStoreRobust
from data_models import AccountData, TransactionData, BillData, SyncResults
from GoogleSheets import appendToSheet
from Walmart import getWalmartReceipt

# Global constants moved here
PUSHNOTIFSCRIPT = "C:/Users/jerro/Documents/SendPushNotification.ps1"
NUMTRANSACTIONS = 15
BALANCEMIN = 5000
HIGHTRANSACTIONTHRESHOLD = 100
ACCOUNT_ID = "3918"

def send_push_notification(message: str):
    """Sends a push notification via PowerShell."""
    result = subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", PUSHNOTIFSCRIPT, message], capture_output=True, text=True, check=False)
    print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Push notification result - {result}")

def find_new_and_updated_transactions(local_transactions: List[TransactionData], web_transactions: List[TransactionData]) -> SyncResults:
    results = SyncResults(new_transactions=[], updated_transactions=[])

    matched_local_ids = set()
    for web_t in web_transactions:
        best_match = None
        for local_t in local_transactions:
            # Skip this local transaction if it's already been matched
            if local_t.id in matched_local_ids:
                continue

            is_same_amount = web_t.withdrawal == local_t.withdrawal and web_t.deposit == local_t.deposit
            date_difference = abs((web_t.date.date() - local_t.date.date()).days)

            if is_same_amount and date_difference <= 3:
                # Critical check for the false positive. If the local transaction is already
                # posted and the new one from the web is pending, this is not a valid match.
                if web_t.status == "pending" and local_t.status == "posted":
                    continue # Skip this match and keep looking

                best_match = local_t
                break

        if best_match:
            # Mark the local transaction as matched
            matched_local_ids.add(best_match.id)
            # Only update if there is a change in status or if the date has changed.
            if web_t.status != best_match.status or date_difference > 0:
                web_t.id = best_match.id  # Ensure the web transaction has the same ID for updating
                web_t.creationTime = best_match.creationTime  # Preserve the original creation time
                results.updated_transactions.append(web_t)
        else:
            # If no valid match was found, this is a truly new transaction.
            results.new_transactions.append(web_t)
                
    return results

def is_walmart(transaction: TransactionData) -> bool:
    """Checks if a transaction is from Walmart based on its description."""
    return re.search('WM SUPERCENT|WAL-MART', transaction.description) is not None

def extract_walmart_details(transaction: TransactionData):
    """Extracts store ID and card digits from a Walmart transaction description."""
    storeId_match = re.search('(?<=#)[0-9]+', transaction.description)
    cardDigits_match = re.search('(?<=CARD )[0-9]+', transaction.description)
    date_match = re.search('(?<= ON )[0-9]{2}/[0-9]{2}', transaction.description)
    
    if storeId_match and cardDigits_match and date_match:
        return {
            'date': datetime.strptime(date_match.group() + f"/{transaction.date.year}", '%m/%d/%Y').strftime("%m-%d-%Y"),
            'total': transaction.withdrawal,
            'store': storeId_match.group(),
            'card': cardDigits_match.group()
        }
    else:
        return None

def append_walmart_receipt_data(walmart_transactions: List[dict]):
    """Fetches Walmart receipt data and appends it to the Google Sheet."""
    spreadsheetwalmartdata = []
    first_transaction = True
    for w in walmart_transactions:
        if not first_transaction:
            print(f"Sleeping 10 seconds before pulling next Walmart data")
            time.sleep(10)
        first_transaction = False
        print(f"Attempting to pull Walmart receipt data - {w}")
        walmartdata = getWalmartReceipt(w)
        for d in walmartdata:
            for i in d:
                datestr = datetime.strptime(i['date'], '%m-%d-%y %H:%M:%S').strftime("%m/%d/%Y %H:%M:%S")
                spreadsheetwalmartdata.append([i['order'], datestr, i['description'], i['price']])
    if len(spreadsheetwalmartdata) > 0:
        appendToSheet(spreadsheetwalmartdata, '149370kuuV-ifi98q1Bb9-_DMsiwoGz3o7qkG8oYrOZw', 'Purchases')

def process_and_sync_transactions(browser_data: AccountData, api_store: ApiDataStoreRobust):
    """The core logic for syncing data and checking bills."""
    # Check balance and send notifications if needed
    if browser_data.balance < BALANCEMIN:
        send_push_notification(f"Balance low - ${browser_data.balance}")
    
    api_store.update_balance(browser_data.balance)
    api_store.update_monitor(browser_data.balance)
    
    # Get local data
    local_transactions = api_store.get_last_transactions(ACCOUNT_ID, NUMTRANSACTIONS * 2)
    bill_array = api_store.get_bill_array()
    
    # Store original bill statuses for later comparison
    orig_bill_statuses = {bill.bill_id: bill.payed for bill in bill_array}
    
    # Compare and find new transactions and updates
    sync_data = find_new_and_updated_transactions(local_transactions, browser_data.transactions)

    for t in sync_data.updated_transactions:
        if t.status == "posted":
            print(f"Updating transaction {t.description} to posted status.")
        else:
            print(f"Updating pending transaction date {t.description}")
        api_store.update_transaction(t.id, t)
    
    # Reverse new transactions to add in the correct chronological order
    new_transactions = list(reversed(sync_data.new_transactions))
    
    # Add new transactions to the API and check for paid bills
    for new_transaction in new_transactions:
        print(f"Adding Transaction {new_transaction.description} to local database.")
        api_store.add_transaction(new_transaction, ACCOUNT_ID)
        check_transaction(new_transaction, bill_array, is_payed=True)
    
    # Update bills in the database that have a changed status
    for bill in bill_array:
        if bill.payed != orig_bill_statuses.get(bill.bill_id, None):
            print(f"Updating database for {bill.title} bill status - {bill.payed}")
            send_push_notification(f"Bill updated - {bill.title}")
            api_store.pay_bill(bill)
    
    #Update Google Sheets with new and updated transactions
    transaction_spreadsheet_queue = []
    walmart_spreadsheet_queue = []

    for t in sync_data.updated_transactions:
        if t.status == "posted":
            amount = -t.withdrawal if t.withdrawal > 0 else t.deposit
            transaction_spreadsheet_queue.append([t.date.strftime("%m/%d/%Y"), amount, t.description])
            if is_walmart(t):
                walmart_spreadsheet_queue.append(extract_walmart_details(t))

    for t in new_transactions:
        if t.status == "posted":
            amount = -t.withdrawal if t.withdrawal > 0 else t.deposit
            transaction_spreadsheet_queue.append([t.date.strftime("%m/%d/%Y"), amount, t.description])
            if is_walmart(t):
                walmart_spreadsheet_queue.append(extract_walmart_details(t))

    if len(transaction_spreadsheet_queue) > 0:
        appendToSheet(transaction_spreadsheet_queue)
    if len(walmart_spreadsheet_queue) > 0:
        append_walmart_receipt_data(walmart_spreadsheet_queue)

def check_transaction(transaction: TransactionData, bill_array: List[BillData], is_payed: bool):
    """Logic to check if a transaction pays a bill."""
    sorted_bills = sorted(bill_array, key=lambda b: b.due_date)
    first_bill_match = True
    for bill in sorted_bills:
        if first_bill_match and transaction.withdrawal >= bill.amount and bill.payed != is_payed:
            if re.search(bill.transaction_regex, transaction.description): # Note: Regex should be on a specific pattern, not the title
                print(f"Changing {bill.title} bill status - {is_payed}")
                bill.payed = is_payed
                first_bill_match = False
    
    if first_bill_match and transaction.withdrawal >= HIGHTRANSACTIONTHRESHOLD:
        print("Transaction over $100 was made")
        send_push_notification("High transaction was made")

if __name__ == "__main__":
    debug = False
    if len(sys.argv) > 1:
        first_argument = sys.argv[1]
        if first_argument.lower() == "-debug":
            debug = True
            print("Debug mode enabled")
    browser_retriever = BrowserDataRetriever()
    if debug:
        api_store = ApiDataStoreRobust(api_url="https://mr-badass/api")
    else:
        api_store = ApiDataStoreRobust()

    # The main script now orchestrates the process with simple function calls
    try:
        browser_data = browser_retriever.retrieve_all_data(ACCOUNT_ID, NUMTRANSACTIONS)
        process_and_sync_transactions(browser_data, api_store)
    except Exception as e:
        send_push_notification(f"Exception: {e}")

    print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Finished checking account")