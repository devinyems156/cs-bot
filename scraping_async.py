import aiohttp
# import asyncio
from bs4 import BeautifulSoup


async def get_steam_user_info(steam_id):
    url = f'https://steamcommunity.com/profiles/{steam_id}/'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            # print(response.status)
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            nickname_element = soup.select_one('.actual_persona_name')
            description_element = soup.select_one('.profile_summary')
            avatar_elements = soup.select('.playerAvatarAutoSizeInner img')
            avatar_element = avatar_elements[-1]

            nickname = nickname_element.text.strip() if nickname_element else "Nickname not found"
            description = description_element.text.strip() if description_element else "Description not found"
            avatar = avatar_element['src'] if avatar_element else "Avatar not found"

            return {
                'nickname': nickname,
                'description': description,
                'avatar': avatar
            }


# async def main():
#     # Steam user ID (replace with the ID of the user you want to scrape)
#     steam_id = '76561198979251405'
#
#     user_info = await get_steam_user_info(steam_id)
#
#     if user_info:
#         print(f"Nickname: {user_info['nickname']}")
#         print(f"Description: {user_info['description']}")
#         print(f"Avatar Link: {user_info['avatar']}")
#     else:
#         print("Failed to retrieve user information. Make sure the Steam ID is valid.")
#
#
# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(main())

