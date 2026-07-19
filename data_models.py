# data_models.py
from datetime import datetime
from typing import List, Dict, Union

class TransactionData:
    """A data object to represent a single transaction."""
    def __init__(self, withdrawal: float, deposit: float, description: str, status: str, date: datetime, id: int = 0, creationTime: datetime=datetime.now()):
        self.withdrawal = withdrawal
        self.deposit = deposit
        self.description = description
        self.status = status
        self.date = date
        self.id = id
        self.creationTime = creationTime
    
    def __repr__(self):
        return f"Transaction(withdrawal={self.withdrawal}, deposit={self.deposit}, description='{self.description[:10]}...', date='{self.date}', status='{self.status}')"

class BillData:
    """A data object to represent a single bill."""
    def __init__(self, bill_id: str, title: str, amount: float, payed: bool, due_date: datetime, transaction_regex: str):
        self.bill_id = bill_id
        self.title = title
        self.amount = amount
        self.payed = payed
        self.due_date = due_date
        self.transaction_regex = transaction_regex

class AccountData:
    """A comprehensive data object for all retrieved account information."""
    def __init__(self, balance: float, transactions: List[TransactionData], offer_found = False):
        self.balance = balance
        self.transactions = transactions
        self.offer_found = offer_found

class SyncResults:
    """A data object representing the segregated outcome of a transaction sync."""
    def __init__(self, new_transactions: List[TransactionData] = None, updated_transactions: List[TransactionData] = None):
        self.new_transactions = new_transactions if new_transactions is not None else []
        self.updated_transactions = updated_transactions if updated_transactions is not None else []