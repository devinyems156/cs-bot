from __future__ import annotations

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase


class Database:
    def __init__(self, mongodb_uri: str):
        self.mongodb_uri = mongodb_uri
        loop = asyncio.get_running_loop()
        loop.create_task(self._init_database())
        print('[INFO ] Database initializing scheduled')
        self.users_collection: AsyncIOMotorCollection = None
        self.roles_collection: AsyncIOMotorCollection = None

    async def _init_database(self):
        print('[INFO ] Initializing database...')
        client = AsyncIOMotorClient(self.mongodb_uri)
        db: AsyncIOMotorDatabase = client.get_database('cs_bot')
        # print(db)
        self.users_collection = db.get_collection('users_collection')
        self.roles_collection = db.get_collection('roles_collection')
        print('[INFO ] Database connection established')

    async def create_user(self, user_id: int, steam_id: int, verified: bool = False, total: int = 0,
                          code: str = None, last_check: int = 0) -> bool:
        if await self.users_collection.find_one({'_id': user_id}) is None:
            user = {'_id': user_id,
                    'steam_id': steam_id,
                    'verified': verified,
                    'total': total,
                    'code': code,
                    'last_check': last_check,
                    'items': 0,
                    'verify_attempts': 0,
                    }
            await self.users_collection.insert_one(user)
            return True
        return False

    async def update_user(self, user_id: int, steam_id: int = None, verified: bool = None, total: int = None,
                          code: str = None, last_check: int = None, items: int = None, verify_attempts: int = None):
        user = await self.users_collection.find_one({'_id': user_id})
        if not user:
            return False
        if steam_id is not None:
            user['steam_id'] = steam_id
        if verified is not None:
            user['verified'] = verified
        if total is not None:
            user['total'] = total
        if code is not None:
            user['code'] = code
        if last_check is not None:
            user['last_check'] = last_check
        if items is not None:
            user['items'] = items
        if verify_attempts is not None:
            user['verify_attempts'] = verify_attempts
        await self.users_collection.replace_one({'_id': user_id}, user)

    async def get_next_user(self):
        cursor = self.users_collection.aggregate([{'$match': {'verified': True}},{'$sort': {'last_check': 1}}])
        user = await cursor.next()
        return user

    async def get_user(self, user_id: int) -> dict | None:
        user = await self.users_collection.find_one({'_id': user_id})
        return user

    async def add_role(self, role_id: int, cost: float | int) -> bool:
        if await self.roles_collection.find_one({'_id': role_id}) is None:
            role = {'_id': role_id, 'cost': cost}
            self.roles_collection.insert_one(role)
            return True
        return False

    async def update_role(self, role_id: int, cost: float | int) -> bool:
        role = await self.roles_collection.find_one({'_id': role_id})
        if role is None:
            await self.add_role(role_id, cost)
            return False
        else:
            role['cost'] = cost
            await self.roles_collection.replace_one({'_id': role_id}, role)
            return True

    async def remove_role(self, role_id):
        if await self.roles_collection.find_one({'_id': role_id}):
            self.roles_collection.delete_one({'_id': role_id})
            return True
        return False

    async def get_all_roles(self):
        roles = {}
        cursor = self.roles_collection.find()
        item = await cursor.next()
        while item is not None:
            roles[item['_id']] = item
            try:
                item = await cursor.next()
            except StopAsyncIteration:
                break
        # print(roles)
        return roles


# user = users_collection.find_one({'_id': user_id})
# print(user)

# user = {'_id': user_id,
#         'steam_id': steam_id,
#         'verified': verified,
#         'total_price': 0,}
#
# # users_collection.insert_one(user)
# users_collection.update_one({'_id': user_id}, {'verified': True})


# async def test():
#     MONGODB_URI = \
#         "mongodb+srv://devinyems156:UOffRFShBdQbS1rQ@cluster0.cqbnfsc.mongodb.net/?retryWrites=true&w=majority"
#     db = Database(MONGODB_URI)
#     user_id = 1234421241
#     steam_id = 76561198073924626
#     verified = False
#     await asyncio.sleep(5)
#     await db.create_user(user_id, steam_id, verified)
#     # await db.update_user(user_id, verified=True)
#     # print(await db.get_user(user_id))
#     # role_id = 1451152241414
#     # cost = 102
#     # await db.add_role(role_id, cost)
#     # await db.get_all_roles()
#     print(await db.get_next_user())
#
# if __name__ == '__main__':
#     asyncio.run(test())

