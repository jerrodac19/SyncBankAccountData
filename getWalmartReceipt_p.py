from playwright.sync_api import sync_playwright
import os.path
import time
import random

def getWalmartReceipt(receiptInfo):
    #Get Script Path
    workingDir = os.path.dirname(os.path.realpath(__file__))
    user_data_dir = workingDir + '\\browser_profile'
    with sync_playwright() as p:
        browser_args = [
            "--no-sandbox", # Essential for some Linux environments
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled", # Directly fights some automation flags
            "--disable-infobars", # Removes "Chrome is being controlled by automated test software"
            "--disable-extensions", # Prevents loading extensions that might be detectable
            "--mute-audio", # Some sites check audio capabilities
            "--disable-dev-shm-usage", # Addresses shared memory issues on Linux/Docker
            "--start-maximized", # Simulate a maximized window (even headless)
        ]
        # Browser setup and stealth settings...
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            channel='chrome',
            headless=True,
            args=browser_args,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = context.pages[0]
        context.add_init_script(path=workingDir + '\\getWalmartReceiptData.js')
        recieptdata = []
        try:
            page.goto("https://www.walmart.com/receipt-lookup", timeout=60000)
            for r in receiptInfo:
                try:
                    recieptdata.append(page.evaluate(f"getReceiptItems('{r['date']}', '{r['total']}', '{r['card']}', '{r['store']}')"))
                except Exception as e:
                    print(f"error reading walmart reciept data - {e}");
        except Exception as e:
            print(f"error loading walmart page - {e}")
    return recieptdata
"""
data = getWalmartReciepts()
for i in data:
    print(i)
"""