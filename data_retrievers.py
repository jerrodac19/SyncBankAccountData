# data_retrievers.py
from abc import ABC, abstractmethod
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import random
import re
from datetime import datetime, timedelta
import keyring
import requests
from typing import List, Optional, Any
import os.path

from data_models import AccountData, TransactionData, BillData

# Global constants moved here
ACCOUNTWEBSITE = "https://connect.secure.wellsfargo.com/auth/login/present?origin=cob&LOB=CONS"
LOCALWEBADDRESS = "http://127.0.0.1:1234"
API_BASE_URL = "https://localhost/api"
CA_CERT_PATH = 'C:/certs/rootCA.pem'
ERRORSCREENSHOT1 = "errorscreenshot_navigation.png"
ERRORSCREENSHOT2 = "errorscreenshot_balance.png"
ERRORSCREENSHOT3 = "errorscreenshot_offer.png"
TIMEOUT = 6

# --- Abstract Base Class for Retrieval Strategies ---
class DataRetriever(ABC):
    @abstractmethod
    def retrieve_all_data(self) -> AccountData:
        """Abstract method to retrieve all account data."""
        pass

# --- Browser Automation Class (the new 'main' logic for scraping) ---
class BrowserDataRetriever(DataRetriever):
    def retrieve_all_data(self, accountstring: str, num_transactions: int) -> AccountData:
        print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Starting browser session.")
        workingDir = os.path.dirname(os.path.realpath(__file__))
        user_data_path = os.path.join(workingDir, "browser_profile")
        with sync_playwright() as p:
            #create a simulated page to mimic human interaction
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
                "--mute-audio",
                "--disable-dev-shm-usage",
                "--start-maximized"
            ]

            # Persistent context replaces the need to manually load/save storageState
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                headless=True,
                args=browser_args,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/Phoenix",
                geolocation={"latitude": 33.424768, "longitude": -111.738027, "accuracy": 100},
                permissions=['geolocation']
            )
            
            page = context.pages[0] if context.pages else context.new_page()
            stealth_sync(page)

            time.sleep(random.uniform(3, TIMEOUT))
            
            # Login and navigation logic (moved from get_balance)
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Navigating to {ACCOUNTWEBSITE}")
            page.goto(ACCOUNTWEBSITE, timeout=60000)
            try:
                page.wait_for_load_state("domcontentloaded")
            except Exception as e:
                print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Excpetion waiting for webpage to load: {e}")
                page.screenshot(path=ERRORSCREENSHOT1)
                print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Screenshot saved to {ERRORSCREENSHOT1}")
            
            time.sleep(1)
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Attempting Login")
            usernamefield = "#j_username"
            username = "jerrodac18"
            passwordfield = "#j_password"
            password = keyring.get_password('WellsFargo', username)
            signonbutton = "xpath=//button[text() = 'Sign on']"
            if password == None:
                raise ValueError("WellsFargo Password not found")
            
            try:
                page.wait_for_selector(usernamefield)
                page.locator(usernamefield).wait_for(state="visible")
                page.locator(usernamefield).wait_for(state="attached")
                page.locator(usernamefield).type(username, delay=random.randint(60, 150))
                page.locator(passwordfield).type(password, delay=random.randint(60, 150))
                page.locator(signonbutton).click()
                page.wait_for_load_state("networkidle")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Exception in logging in: {e}")
            
            self._check_for_and_reject_offer(page)
            
            # Add human noise only when on the dashboard
            self._human_behavior(page)
            
            # Get balance
            try:
                balance = self._get_balance(page)
            except Exception as e:
                print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Exception in getting balance: {e}")
                context.close()
                raise e

            # Get transactions
            transactions = self._get_next_transactions(page, accountstring, num_transactions)
            
            # Sign off and close
            yesbuttonsignoff = "xpath=//button[span='Yes']"
            page.locator("xpath=//button[div='Sign Off']").click()
            self._wait_for_page_item(page, yesbuttonsignoff, TIMEOUT)
            page.locator(yesbuttonsignoff).click()
            page.wait_for_load_state("networkidle")
            time.sleep(random.uniform(3, TIMEOUT))
            self._wait_for_page_item(page, "xpath=//h1[text()='Thanks for visiting']", TIMEOUT)
            
            context.close()
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Browser session finished.")
            
            return AccountData(balance, transactions)
            
    def _human_behavior(self, page):
        # Combined scrolling and mouse movement
        viewport = page.viewport_size
        x = random.randint(100, viewport['width'] - 100)
        y = random.randint(100, viewport['height'] - 100)
        page.mouse.move(x, y, steps=10)
        page.evaluate(f"window.scrollBy(0, {random.randint(200, 400)})")
        time.sleep(random.uniform(0.5, 1.2))
    
    def _check_for_and_reject_offer(self, page):
        no_thanks = page.get_by_text("No thanks")
        view_offer = page.get_by_text("View your offer")
        income = page.get_by_text("Update my income")
        infomessage = page.get_by_text("Continue to online banking")
        if (no_thanks.count() > 0 and (view_offer.count() > 0 or income.count() > 0)):
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Offer found")
            page.screenshot(path=ERRORSCREENSHOT3)
            no_thanks.click()
        elif (infomessage.count() > 0):
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} info page found")
            page.screenshot(path=ERRORSCREENSHOT3)
            infomessage.click()
    
    def _get_balance(self, page) -> float:
        """Internal helper to get the account balance."""
        balance_selector = "span[data-testid='EVERYDAY CHECKING-balance']"
        self._wait_for_page_item(page, balance_selector, TIMEOUT)
        
        if page.locator(balance_selector).count() > 0:
            balance = float(page.locator(balance_selector).nth(1).text_content().replace("$", "").replace(",", ""))
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Balance found - ${balance}")
        else:
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Unable to find balance")
            page.screenshot(path=ERRORSCREENSHOT2)
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Screenshot saved to {ERRORSCREENSHOT2}")
            raise ValueError("Unable to find balance")
        
        return balance

    def _get_next_transactions(self, page, account, numberoftransactions) -> List[TransactionData]:
        """Internal helper to scrape transactions from the webpage."""
        date_format_string = "%m/%d/%y"
        page.locator(f"xpath=//span[text()='...{account}']").click()
        self._wait_for_page_item(page, "xpath=//tbody/tr", TIMEOUT)
        
        transactions = []
        status_str = "pending"
        purchases = page.locator("xpath=//tbody/tr")
        for n in range(purchases.count()):
            if len(transactions) >= numberoftransactions:
                break
            
            row_text = purchases.nth(n).text_content()
            if re.search("Posted Transactions" , row_text):
                status_str = "posted"
            if not re.search("(Pending|Posted|Authorized) Transactions|Received for Processing", row_text):
                cols = purchases.nth(n).locator("td")
                if cols.count() > 4:
                    withdrawal_str = cols.nth(4).text_content().replace("$", "").replace(",", "")
                    deposit_str = cols.nth(3).text_content().replace("$", "").replace(",", "")
                    
                    transactions.append(TransactionData(
                        withdrawal=float(withdrawal_str) if withdrawal_str else 0.0,
                        deposit=float(deposit_str) if deposit_str else 0.0,
                        description=re.sub(' +',' ',cols.nth(2).text_content()),
                        status=status_str,
                        date=datetime.strptime(cols.nth(1).text_content(), date_format_string)
                    ))
        
        page.locator("xpath=//span[text()='Account Summary']").click()
        page.wait_for_load_state("networkidle")
        return transactions

    def _wait_for_page_item(self, page, itemstring, timeout):
        """Internal helper for waiting on page elements."""
        waittime = 0
        try:
            item = page.locator(itemstring)
        except Exception as e:
            print(f"{time.strftime('%m/%d/%y %H:%M:%S', time.localtime())} Excpetion finding page element '{itemstring}': {e}")
        while waittime < timeout and item.count() == 0:
            time.sleep(0.5)
            waittime += 0.5
            
# --- API Client Class (the new 'bill_functions' logic) ---
#old api (outdated)
class ApiDataStore:
    def get_last_transactions(self, account: str, number_of_transactions: int) -> List[TransactionData]:
        date_format_string = "%Y-%m-%d %H:%M:%S.000000"
        data = self._get_web_request(f"{LOCALWEBADDRESS}/Transactions.php?GroupID=1&AccountName={account}&Number={number_of_transactions}")
        if not data:
            return []
        
        return [
            TransactionData(
                withdrawal=float(d["Withdrawal"]),
                deposit=float(d["Deposit"]),
                description=d["Description"],
                status=d["Status"],
                date=datetime.strptime(d["Date"]["date"], date_format_string)
            ) for d in data
        ]

    def add_transaction(self, transaction: TransactionData, account: str):
        web_description = transaction.description.replace("%", "%25").replace("#", "%23").replace("&", "%26").replace("+", "%2B")
        self._get_web_request(f"{LOCALWEBADDRESS}/AddTransaction.php?GroupID=1&Withdrawal={transaction.withdrawal}&Deposit={transaction.deposit}&Description={web_description}&Date={transaction.date}&Status={transaction.status}&AccountName={account}")

    def get_bill_array(self) -> List[BillData]:
        data = self._get_web_request(f"{LOCALWEBADDRESS}/bills.php")
        if not data:
            return []
            
        return [
            BillData(
                bill_id=d["Id"],
                title=d["Title"],
                amount=float(d["Amount"]),
                payed=d["Payed"],
                due_date=d["DueDate"]["date"] # Note: The original code used a dictionary here, which may need to be handled more gracefully if it's not a standard datetime object.
            ) for d in data
        ]

    def pay_bill(self, bill: BillData):
        self._get_web_request(f"{LOCALWEBADDRESS}/updatebill.php?Id={bill.bill_id}&Payed={bill.payed}")

    def update_balance(self, balance: float):
        self._get_web_request(f"{LOCALWEBADDRESS}/UpdateBalance.php?Amount={balance}")

    def update_monitor(self, balance: float):
        self._get_web_request(f"{LOCALWEBADDRESS}/UpdateMonitor.php?Amount={balance}")
        
    def _get_web_request(self, url: str):
        """Internal helper for making API requests."""
        response = requests.get(url)
        if response.status_code == 200:
            try:
                return response.json()
            except:
                return None
        else:
            print(f"Request failed with status code: {response.status_code}")
            return None
            
class ApiDataStoreRobust:
    def _make_request(self, method: str, url: str, data: Optional[Any] = None):
        """Internal helper for making API requests."""
        try:
            headers = {'Content-Type': 'application/json'}
            if method == "GET":
                response = requests.get(url, headers=headers, verify=CA_CERT_PATH)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, verify=CA_CERT_PATH)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers, verify=CA_CERT_PATH)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status() # Raises an HTTPError if the status is 4xx, 5xx
            
            if response.status_code == 204:
                return None
            
            return response.json()
        except requests.exceptions.HTTPError as errh:
            print(f"Http Error: {errh}")
            print(f"Response body: {errh.response.text}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
        return None

    def get_last_transactions(self, account: str, number_of_transactions: int) -> List[TransactionData]:
        url = f"{API_BASE_URL}/transactions?n={number_of_transactions}&accountName={account}"
        data = self._make_request("GET", url)
        if not data:
            return []
        
        return [
            TransactionData(
                withdrawal=d["withdrawal"],
                deposit=d["deposit"],
                description=d["description"],
                status=d["status"],
                date=datetime.fromisoformat(d["date"]),
                id=d["id"],
                creationTime=datetime.fromisoformat(d["creationTime"].split(".")[0]) + timedelta(hours=-7)
            ) for d in data
        ]

    def add_transaction(self, transaction: TransactionData, account: str):
        url = f"{API_BASE_URL}/transactions"
        transaction_dto = {
            "withdrawal": transaction.withdrawal,
            "deposit": transaction.deposit,
            "description": transaction.description,
            "date": transaction.date.isoformat(),
            "status": transaction.status,
            "accountName": account
        }
        self._make_request("POST", url, data=transaction_dto)
        
    def update_transaction(self, id: int, transaction: TransactionData):
        url = f"{API_BASE_URL}/transactions/{id}"
        transaction_dto = {
            "description": transaction.description,
            "date": transaction.date.isoformat(),
            "status": transaction.status
        }
        self._make_request("PUT", url, data=transaction_dto)

    def get_bill_array(self) -> List[BillData]:
        url = f"{API_BASE_URL}/bills"
        data = self._make_request("GET", url)
        if not data:
            return []
        
        return [
            BillData(
                bill_id=d["id"],
                title=d["title"],
                amount=d["amount"],
                payed=d["payed"],
                due_date=datetime.fromisoformat(d["dueDate"]),
                transaction_regex=d["configuration"]["transactionRegex"]
            ) for d in data
        ]

    def pay_bill(self, bill: BillData):
        url = f"{API_BASE_URL}/bills/{bill.bill_id}"
        update_dto = {
            "id": bill.bill_id,
            "payed": bill.payed
        }
        self._make_request("PUT", url, data=update_dto)
        
    def update_balance(self, balance: float):
        url = f"{API_BASE_URL}/accountbalances"
        balance_dto = {
            "amount": balance
        }
        self._make_request("POST", url, data=balance_dto)

    def update_monitor(self, balance: float):
        url = f"{API_BASE_URL}/balancemonitors"
        monitor_dto = {
            "amount": balance
        }
        self._make_request("POST", url, data=monitor_dto)