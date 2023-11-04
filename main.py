import datetime
import random
import asyncio
import os

import discord
import dotenv

from steam_api import get_prices, get_total_price_by_price_list
from database_async import Database
from scraping_async import get_steam_user_info

bot = discord.Bot()


dotenv.load_dotenv()
GUILD_ID = int(os.getenv('GUILD_ID'))
MONGODB_URI = os.getenv('MONGODB_URI')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# STEAM_API_KEY = '7B38EFA91A463A1744C5CCD4FE46792B'  # os.getenv('STEAM_TOKEN')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL'))
USER_INTERVAL = int(os.getenv('USER_INTERVAL'))
PRICES_INTERVAL = int(os.getenv('PRICES_INTERVAL'))
embed_color = int(os.getenv('EMBED_COLOR'), base=16)  # 0x00FF00

no_mentions = discord.AllowedMentions.none()
administrator_permissions = discord.Permissions.none() + discord.Permissions.administrator

bot.database: Database = None
bot.prices_task = None
bot.prices = None
bot.check_task = None
bot.queue = []

roles = discord.SlashCommandGroup('roles', 'Configuration of roles')
debug = discord.SlashCommandGroup('debug', 'Test commands')


@bot.event
async def on_ready():
    print(f"[INFO ] We have logged in as {bot.user}")
    if bot.database is None:
        bot.database = Database(MONGODB_URI)
    if bot.prices_task is None:
        bot.prices_task = asyncio.get_running_loop().create_task(prices_task())
    if bot.check_task is None:
        bot.check_task = asyncio.get_running_loop().create_task(background_check_task())
    bot.add_view(MyView())
    bot.add_view(MyView3())


@bot.command(description="Sends the bot's latency.")  # this decorator makes a slash command
async def ping(ctx):  # a slash command will be created with the name "ping"
    await ctx.respond(f"Pong! Latency is {bot.latency}")


@roles.command(default_member_permissions=administrator_permissions,
               description='Add role to the database to be given to users')
@discord.option(name='role', input_type=discord.Role,
                description='The role to remove from the list to no longer be added')
@discord.option(name='cost', input_type=float,
                description='Minimal total inventory cost to obtain this role')
async def add(ctx: discord.ApplicationContext, role: discord.Role, cost: float):
    role: discord.Role
    role_id = role.id
    cost = float(cost)
    success = await bot.database.add_role(role_id, cost)
    if success:
        await ctx.respond(f'Role {role.mention} was successfully added to the database and will be given to users with'
                          f' inventory total cost higher than {cost}', allowed_mentions=no_mentions)
    else:
        await ctx.respond(f'Something went wrong... Is {role.mention} already in the list? Use `/roles list` to '
                          f'check it. If so, use `/roles change` instead', allowed_mentions=no_mentions)


@roles.command(default_member_permissions=administrator_permissions,
               description='Change role\'s minimal inventory cost')
@discord.option(name='role', input_type=discord.Role,
                description='The role to change it\'s minimal inventory cost')
@discord.option(name='cost', input_type=float,
                description='New minimal total inventory cost to obtain this role')
async def change(ctx: discord.ApplicationContext, role: discord.Role, cost: float):
    role: discord.Role
    role_id = role.id
    cost = float(cost)
    updated = await bot.database.update_role(role_id, cost)
    if updated:
        await ctx.respond(f'Role {role.mention} was successfully updated and will be given to users with'
                          f'inventory total cost higher than {cost}', allowed_mentions=no_mentions)
    else:
        await ctx.respond(f'There were no {role.mention} yet, so it was added', allowed_mentions=no_mentions)


@roles.command(default_member_permissions=administrator_permissions,
               description='Remove a role from the list')
@discord.option(name='role', input_type=discord.Role,
                description='The role to remove from the list to no longer be added')
async def remove(ctx: discord.ApplicationContext,
                 role: discord.Role):
    role: discord.Role
    role_id = role.id
    result = await bot.database.remove_role(role_id)
    if result:
        await ctx.respond(f'Role {role.mention} was successfully removed from the list and no longer will be added',
                          allowed_mentions=no_mentions)
    else:
        await ctx.respond(f'There were no {role.mention} in the list',
                          allowed_mentions=no_mentions)


@roles.command(default_member_permissions=administrator_permissions,
               description='List all the roles', name='list')
async def list_roles(ctx: discord.ApplicationContext):
    roles_dict: dict = await bot.database.get_all_roles()
    roles = list(roles_dict.values())
    roles.sort(key=lambda x: x['cost'])
    guild = ctx.guild
    roles_text_list = [f'{x["cost"]} - {guild.get_role(x["_id"]).mention}' for x in roles]
    roles_text = "\n".join(roles_text_list)
    text = '### Current roles list: \n' + roles_text
    await ctx.respond(text, allowed_mentions=no_mentions)


@debug.command(default_member_permissions=administrator_permissions)
async def set_steam(ctx: discord.ApplicationContext, steam_id):
    steam_id = int(steam_id)
    user_id = ctx.user.id
    success = await bot.database.update_user(user_id=user_id, steam_id=steam_id, verified=True, last_check=0)
    if not success:
        await bot.database.create_user(user_id=user_id, steam_id=steam_id, verified=True, last_check=0)
    await ctx.respond(f"Steam `{steam_id}` linked successfully")


@bot.command(default_member_permissions=administrator_permissions, name='force-check')
async def force_check(ctx: discord.ApplicationContext):
    user_id = ctx.user.id
    user_info = await bot.database.get_user(user_id)
    if not user_info:
        await ctx.respond('You need to add your account first')
        return
    if not user_info['verified']:
        await ctx.respond('You need to verify your account first')
        return
    ts = user_info['last_check']
    now = int(datetime.datetime.now().timestamp())
    diff = now - ts
    left = USER_INTERVAL - diff
    if left > 0:
        await ctx.respond('Your inventory was checked recently')
        return
    bot.queue.append(user_id)
    await ctx.respond('Checking your inventory was scheduled, please wait')
    await check_user(user_id)


async def prices_task():
    while True:
        print('[INFO ] Prices task: refreshing prices...')
        try:
            bot.prices = await get_prices()
            print('[INFO ] Prices task: prices refreshed')
        except Exception as e:
            print(e, e.args)
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(PRICES_INTERVAL)


async def background_check_task():
    while True:
        try:
            if len(bot.queue) > 0:
                user_id = bot.queue.pop(0)
                user_data = await bot.database.get_user(user_id)
            else:
                user_data = await bot.database.get_next_user()
                user_id = user_data['_id']
            time = int(datetime.datetime.now().timestamp()) - user_data['last_check']
            left = USER_INTERVAL - time
            # print(time, left)
            if left > 0:
                print(f'[INFO ] Next user steam inventory total cost check will be in {left} seconds')
                await asyncio.sleep(left)
            await check_user(user_id)
            await bot.database.update_user(user_id=user_id, last_check=int(datetime.datetime.now().timestamp()))
        except Exception as e:
            print(f"[ERROR] something went wrong: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


async def check_user(user_id):
    user_info = await bot.database.get_user(user_id)
    if not user_info['verified']:
        return
    user_id = user_info['_id']
    steam_id = user_info['steam_id']
    if bot.prices is None:
        while bot.prices is None:
            await asyncio.sleep(60)
    total = await get_total_price_by_price_list(steam_id, bot.prices)
    # total = 1729.52
    roles_dict: dict = await bot.database.get_all_roles()
    roles = list(roles_dict.values())
    roles.sort(key=lambda x: x['cost'])
    # print(roles)
    chosen_role_id = 0
    for i in roles:
        if i['cost'] <= total:
            chosen_role_id = i['_id']
        else:
            continue
    # print(chosen_role_id)
    guild = bot.get_guild(GUILD_ID)
    # print(guild)
    # print(user_id)
    member = guild.get_member(user_id)
    # print(member)
    member = await guild.fetch_member(user_id)
    # print(member)
    if chosen_role_id != 0:
        chosen_role = guild.get_role(chosen_role_id)
        if chosen_role not in member.roles:
            await member.add_roles(chosen_role)
    for i in roles:
        role = guild.get_role(i['_id'])
        if role in member.roles and role.id != chosen_role_id:
            await member.remove_roles(role)
    ts = int(datetime.datetime.now().timestamp())
    await bot.database.update_user(user_id=user_id, last_check=ts)


bot.add_application_command(roles)
bot.add_application_command(debug)


def generate_code():
    length = 10
    chars = 'qwertyuiop[]asdfghjkl;zxcvbnm,./QWERTYUIOP{}ASDFGHJHKL:"|ZXCVBNM<>?1234567890-=!@#$%^&*()_+'
    chars_list = list(chars)
    code = ''.join([random.choice(chars_list) for _ in range(length)])
    # print(code)
    return code


@bot.slash_command(name='connect-steam')
async def connect_steam(ctx: discord.ApplicationContext,
                        steam_id: discord.Option(input_type=int)):
    steam_id = int(steam_id)
    user_id = ctx.user.id
    user_info = await get_steam_user_info(steam_id)
    # print(user_info)
    nickname = user_info['nickname']
    description = user_info['description']
    avatar_url = user_info['avatar']
    code = generate_code()
    if nickname.find(code) != -1:
        while True:
            code = generate_code()
            if nickname.find(code) == -1:
                break
    success = await bot.database.create_user(user_id, steam_id, False, code=code)
    if not success:
        await bot.database.update_user(user_id, steam_id, False, code=code)
    embed = discord.Embed(title=nickname, description=description,
                          color=embed_color)
    embed.add_field(name="Steam ID", value=str(steam_id))
    embed.set_thumbnail(url=avatar_url)
    text = 'Is that your profile?'
    await ctx.respond(content=text, embed=embed, view=MyView())


class MyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # timeout of the view must be set to None

    @discord.ui.button(label="Yes, it's mine", custom_id="button1", style=discord.ButtonStyle.success)
    async def button_callback(self, button, interaction):
        message: discord.Message = interaction.message
        old_interaction: discord.MessageInteraction = message.interaction
        user = interaction.user
        response: discord.InteractionResponse = interaction.response
        if old_interaction.user.id != user.id:
            await response.send_message(content="Oops.. It seems it's not your interaction to "
                                                "click it\'s buttons", ephemeral=True, delete_after=30)
        user_data = await bot.database.get_user(user.id)
        code = user_data['code']
        await response.edit_message(content='To prove it\'s your account, copy this code `' + code +
                                            '`, paste it in your steam nickname (you can remove it after '
                                            'verification is done) and then click '
                                            'the button to verify it', view=MyView3(), embeds=[])

    @discord.ui.button(label="No, it is not", custom_id="button2", style=discord.ButtonStyle.danger)
    async def button_callback2(self, button: discord.Button, interaction: discord.Interaction):
        message: discord.Message = interaction.message
        old_interaction: discord.MessageInteraction = message.interaction
        # print(old_interaction.user)
        user = interaction.user
        response: discord.InteractionResponse = interaction.response
        if old_interaction.user.id != user.id:
            await response.send_message(content="Oops.. It seems it's not your interaction to "
                                                "click it\'s buttons", ephemeral=True, delete_after=30)
        # await interaction.response.send_message("You clicked the button!")
        await response.edit_message(
            content='Then it seems you\'ve entered the wrong steam user id. Please run the command again '
                    'with a correct steam id. If needed, follow the guide',
            view=MyView2(), embeds=[])


class MyView2(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        button = discord.ui.Button(label="Guide", style=discord.ButtonStyle.link,
                                   url='https://help.steampowered.com/en/faqs/view/2816-BE67-5B69-0FEC')
        self.add_item(button)


class MyView3(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Verify', custom_id='button', style=discord.ButtonStyle.primary)
    async def button(self, button, interaction):
        message: discord.Message = interaction.message
        old_interaction: discord.MessageInteraction = message.interaction
        user = interaction.user
        response: discord.InteractionResponse = interaction.response
        if old_interaction.user.id != user.id:
            await response.send_message(content="Oops.. It seems it's not your interaction to "
                                                "click it\'s buttons", ephemeral=True, delete_after=30)
        database_user_info = await bot.database.get_user(user.id)
        steam_id = database_user_info['steam_id']
        # print(steam_id)
        steam_user_info = await get_steam_user_info(steam_id)
        nickname: str = steam_user_info['nickname']
        code: str = database_user_info['code']
        # print(nickname)
        # print(code)
        index = nickname.find(code)
        # print(index)
        response: discord.InteractionResponse = interaction.response
        if index == -1:
            await response.edit_message(content='Oops.. It seems there are no code `' + code +
                                                '` in your steam name. If you didn\'t pasted it yet, '
                                                'you should do it to verify your account', view=MyView3(), embeds=[])
        else:
            await bot.database.update_user(user.id, verified=True)
            await response.edit_message(content='Congratulations, you\'ve successfully verified your account. '
                                                'Now you can return your real nickname', view=None)


if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
