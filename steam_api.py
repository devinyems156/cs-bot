# import json
import aiohttp
# import asyncio


async def get_prices():
    url = 'http://csgobackpack.net/api/GetItemsList/v2/'
    async with aiohttp.ClientSession() as session:
        response = await session.get(url=url, data={'no_details': 'true'})
        response.raise_for_status()
        data = await response.json()

    # with open('file.json', 'w') as f:
    #     json.dump(data, f, indent=4)

    items_data = data['items_list']
    item_prices = {}
    for i in items_data.values():
        if 'price' not in i.keys():
            # wtf.append(i)
            continue
        if i.get('marketable') != 1:
            continue
        if '30_days' not in i['price'].keys() and '7_days' not in i['price'].keys():
            prices = i['price']['all_time']
        elif '7_days' not in i['price'].keys():
            prices = i['price']['30_days']
        else:
            prices = i['price']['7_days']
        average = prices['average']
        item_prices[i['name']] = average
    return item_prices


async def get_inventory(steam_id: int):
    url = f'http://steamcommunity.com/inventory/{steam_id}/730/2'
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        response.raise_for_status()
        # print(f"Failed to retrieve inventory. Status Code: {response.status_code}")
        data = await response.json()
    if 'assets' not in data:
        print(f"[INFO ] No CS:GO inventory items found for user with steam_id {steam_id}")
        return {}

    assets = data['assets']
    descriptions = data['descriptions']
    inventory = {}
    for asset in assets:
        # asset_id = asset['assetid']
        class_id = asset['classid']
        # instance_id = asset['instanceid']
        item: dict = next((desc for desc in descriptions if desc['classid'] == class_id), None)

        if not item:
            break
        name = item.get('market_hash_name', None)
        marketable = item.get('marketable', None)
        if marketable != 1 or name is None:
            continue
        # print(f"Asset ID: {asset_id},  Instance ID: {instance_id}")

        if name in inventory.keys():
            inventory[name] += 1
        else:
            inventory[name] = 1
    # for i in inventory.values():
    #     print(f"Class ID: {i['classid']}, Name: {i['name']}, Amount: {i['amount']}")
    #     print("---")
    return inventory


# async def get_total_price(steam_id):
#     inventory = await get_inventory(steam_id)
#     item_prices = await get_prices()
#     total = 0
#     for item_name, amount in inventory.items():
#         price = item_prices.get(item_name)
#         cost = amount * price
#         total += cost
#
#         print(f"Name: {item_name}, Amount: {amount}, Price: {price}, Cost: {cost}, Total: {total}")
#         print("---")
#
#     print(total)
#     total = round(total, 2)
#     print(total)
#     return total


async def get_total_price_by_price_list(steam_id: int, item_prices: dict):
    inventory = await get_inventory(steam_id)
    total = 0
    for item_name, amount in inventory.items():
        price = item_prices.get(item_name)
        cost = amount * price
        total += cost

        # print(f"Name: {item_name}, Amount: {amount}, Price: {price}, Cost: {cost}, Total: {total}")
        # print("---")

    # print(total)
    total = round(total, 2)
    # print(total)
    return total



# if __name__ == '__main__':
#     loop = asyncio.new_event_loop()
#     steam64_id = 76561198073924626
#     # steam64_id = 76561198082041460
#     task = get_total_price(steam64_id)
#     loop.create_task(task)
#     loop.run_forever()
#     # get_inventory(steam64_id)
#     # get_prices()