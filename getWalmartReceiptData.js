async function lookupreceipt(purchaseDate = "09-29-2025", total = "25.42", cardDigits = "6065", storeId = "2767"){
  const response = await fetch("https://www.walmart.com/chcwebapp/api/receipts?storeId=" + storeId + "&purchaseDate=" + purchaseDate + "&cardType=debit&total=" + total + "&lastFourDigits=" + cardDigits, {
    "headers": {
      "accept": "application/json",
      "accept-language": "en-US,en;q=0.9",
      "content-type": "application/json",
      "downlink": "10",
      "dpr": "1",
      "priority": "u=1, i",
      "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
      "sec-ch-ua-mobile": "?0",
      "sec-ch-ua-platform": "\"Windows\"",
      "sec-fetch-dest": "empty",
      "sec-fetch-mode": "cors",
      "sec-fetch-site": "same-origin"
    },
    "referrer": "https://www.walmart.com/receipt-lookup",
    "body": null,
    "method": "GET",
    "mode": "cors",
    "credentials": "include"
  });
  const result = await response.json();
  return result.receipts[0];
}

async function getReceiptItems(purchaseDate = "09-29-2025", total = "25.42", cardDigits = "6065", storeId = "2767"){
  const itempricelist = [];
  const r = await lookupreceipt(purchaseDate, total, cardDigits, storeId);
  const orderid = r.tcNumber;
  const orderdate = r.dateTime
  const ordertax = r.total.taxTotal
  for (const i of r.items){
    itempricelist.push({"order": orderid, "date": orderdate, "description": i.description, "price": i.price})
  }
  itempricelist.push({"order": orderid, "date": orderdate, "description": "TAX", "price": ordertax})
  return itempricelist;
}