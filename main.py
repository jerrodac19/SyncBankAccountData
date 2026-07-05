# main.py
import time
import subprocess
import os
import random
import re
from collections import Counter
from typing import List
from datetime import datetime

from data_retrievers import BrowserDataRetriever, ApiDataStoreRobust
from data_models import AccountData, TransactionData, BillData
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

def compare_and_find_new_transactions(local_transactions: List[TransactionData], web_transactions: List[TransactionData]) -> List[TransactionData]:
    """Compares two lists of transactions to find new ones."""
    def canonicalize_transaction(t: TransactionData):
        if t.status == "posted":
            return (t.withdrawal, t.deposit, t.description, t.date, t.status)
        else: # status is "pending"
            return (t.withdrawal, t.deposit, t.description, t.status)

    local_counter = Counter(canonicalize_transaction(t) for t in local_transactions)
    new_transactions = []
    
    for web_t in web_transactions:
        canonical_web_t = canonicalize_transaction(web_t)
        if local_counter.get(canonical_web_t, 0) > 0:
            local_counter[canonical_web_t] -= 1
        else:
            new_transactions.append(web_t)
            
    return new_transactions

# main.py
# ... (imports) ...

def sync_and_find_new_transactions(local_transactions: List[TransactionData], web_transactions: List[TransactionData], api_store: ApiDataStoreRobust) -> List[TransactionData]:
    """
    Intelligently syncs transactions by finding the best match for updates and adding new ones.
    This version correctly handles one-to-one mapping to prevent false positives.
    """
    matched_local_ids = set() # Use a set for efficient lookups
    
    new_transactions = []
    spreadsheettransactiondata = []
    walmarttransactions = []
    spreadsheetwalmartdata = []

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
            # Only update if the local status is 'pending' and the web status is 'posted'.
            if web_t.status == "posted" and best_match.status == "pending":
                print(f"Updating transaction {best_match.description} to posted status.")
                api_store.update_transaction(best_match.id, web_t)
                if web_t.withdrawal > 0:
                    amount = 0-web_t.withdrawal
                else:
                    amount = web_t.deposit
                spreadsheettransactiondata.append([web_t.date.strftime("%m/%d/%Y"), amount, web_t.description])
                if re.search('WM SUPERCENT|WAL-MART', web_t.description):
                    storeId = re.search('(?<=#)[0-9]+', web_t.description).group()
                    cardDigits = re.search('(?<=CARD )[0-9]+', web_t.description).group()
                    walmarttransactions.append({'date' : best_match.creationTime.strftime('%m-%d-%Y'), 'total' : web_t.withdrawal, 'card' : cardDigits, 'store': storeId})
            if web_t.status == "pending" and best_match.status == "pending" and date_difference > 0:
                print(f"Updating pending transaction date {best_match.description}")
                api_store.update_transaction(best_match.id, web_t)
        else:
            # If no valid match was found, this is a truly new transaction.
            new_transactions.append(web_t)
            if web_t.status == "posted":
                if web_t.withdrawal > 0:
                    amount = 0-web_t.withdrawal
                else:
                    amount = web_t.deposit
                spreadsheettransactiondata.append([web_t.date.strftime("%m/%d/%Y"), amount, web_t.description])
                if re.search('WM SUPERCENT|WAL-MART', web_t.description):
                    storeId = re.search('(?<=#)[0-9]+', web_t.description).group()
                    cardDigits = re.search('(?<=CARD )[0-9]+', web_t.description).group()
                    walmarttransactions.append({'date' : best_match.creationTime.strftime('%m-%d-%Y'), 'total' : web_t.withdrawal, 'card' : cardDigits, 'store': storeId})
            
    if len(spreadsheettransactiondata) > 0:
        appendToSheet(spreadsheettransactiondata)
    if len(walmarttransactions) > 0:
        for w in walmarttransactions:
            print(f"attempting to pull walmart receipt data - {w}")
            walmartdata = getWalmartReceipt([w])
            print(f"sleeping 10 seconds before pulling next walmart data")
            time.sleep(10)
            for d in walmartdata:
                for i in d:
                    datestr = datetime.strptime(i['date'], '%m-%d-%y %H:%M:%S').strftime("%m/%d/%Y %H:%M:%S")
                    spreadsheetwalmartdata.append([i['order'],datestr,i['description'],i['price']])
        if len(spreadsheetwalmartdata) > 0:
            appendToSheet(spreadsheetwalmartdata, '149370kuuV-ifi98q1Bb9-_DMsiwoGz3o7qkG8oYrOZw', 'Purchases')
    
    return new_transactions

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
    
    # Compare and find new transactions
    #new_transactions = compare_and_find_new_transactions(local_transactions, browser_data.transactions)
    new_transactions = sync_and_find_new_transactions(local_transactions, browser_data.transactions, api_store)
    
    # Reverse new transactions to add in the correct order
    new_transactions.reverse()
    
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
    browser_retriever = BrowserDataRetriever()
    api_store = ApiDataStoreRobust()

    # The main script now orchestrates the process with simple function calls
    try:
        browser_data = browser_retriever.retrieve_all_data(ACCOUNT_ID, NUMTRANSACTIONS)
        process_and_sync_transactions(browser_data, api_store)
    except Exception as e:
        send_push_notification(f"Exception: {e}")

    print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Finished checking account")