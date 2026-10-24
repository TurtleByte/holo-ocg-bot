import discord
import os
from dotenv import load_dotenv
import csv
from bs4 import BeautifulSoup
import re
import locale
import urllib.request
import codecs
import asyncio, requests
from datetime import datetime, timezone, timedelta
import pandas as pd
from discord.ext import commands
from discord import app_commands
import typing

# discord token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# sets Intents
intents = discord.Intents.default()

# defining the bot
bot = commands.Bot(case_insensitive=True, command_prefix='!', help_command=None, intents=intents)

@bot.event
async def setup_hook():
    await bot.add_cog(MainCog(bot))
    await bot.tree.sync()
    print("Slash commands synced globally. (Note: Can take up to an hour to propagate in Discord)")

# Event: when bot is ready
@bot.event
async def on_ready():
    startupRoutine()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    bot.loop.create_task(pollCheck())

class Card:
    def __init__(self, setcode, name, image, type, rarity, color, life, tags, batonpass, text, pack, metatags):
        self.setcode = setcode
        self.name = name
        self.image = image
        self.type = type
        self.rarity = rarity
        self.color = color
        self.life = life
        self.tags = tags
        self.text = text
        self.pack = pack
        self.metatags = metatags
        self.batonpass = batonpass
        self.priceDict = {}
        self.priceDupeDict = {}
        self.enPriceDict = {}
        self.enPriceDupeDict = {}

    def addPrice(self, thing):
        if thing.rarity not in self.priceDict:
            self.priceDict[thing.rarity] = thing
        else:
            if thing.rarity not in self.priceDupeDict:
                self.priceDupeDict[thing.rarity] = 1
            else:
                self.priceDupeDict[thing.rarity] += 1
            self.priceDict[thing.rarity + str(self.priceDupeDict[thing.rarity])] = thing

    def addENPrice(self, thing):
        if thing.rarity not in self.enPriceDict:
            self.enPriceDict[thing.rarity] = thing
        else:
            if thing.rarity not in self.enPriceDupeDict:
                self.enPriceDupeDict[thing.rarity] = 1
            else:
                self.enPriceDupeDict[thing.rarity] += 1
            self.enPriceDict[thing.rarity + str(self.enPriceDupeDict[thing.rarity])] = thing
        
class CardPrice:
    def __init__(self, rarity, price, url):
        self.rarity = rarity
        self.price = price
        self.url = url

class Ruling:
    def __init__(self, number, question, answer):
        self.number = int(number)
        self.question = question
        self.answer = answer


bpCount = 8
sdCount = 16
ebCount = 1
pricecsvs = []
cardDict = {}
rulingDict = {}
historyDict = {}

history_df = pd.DataFrame() 

async def pollCheck():
    """Background task to check for TCGCSV updates."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        res = requests.get("https://tcgcsv.com/last-updated.txt", headers={"User-Agent": "HoloOCGBot/0.1.1"})
        timestamp_str = res.text.strip()
        last_updated = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.now(timezone.utc)
        delta = now - last_updated
        
        if delta <= timedelta(minutes=6):
            print(f"TCGCSV last updated {delta.seconds} seconds ago — within 6 minutes. Updating prices...")
            startupRoutine()
        else:
            print(f"TCGCSV last updated {delta} ago. Rechecking in 5m.")

        await asyncio.sleep(5 * 60)

def acronymize(string):
    if "Secret Rare" in string:
        return "SEC"
    elif "Double Rare" in string:
        return "RR"
    else:
        return "".join(e[0] for e in string.split())

def startupRoutine():
    global cardDict, rulingDict, historyDict, pricecsvs

    pricecsvs = []
    cardDict = {}
    rulingDict = {}
    historyDict = {}

    with open('mastersheet.csv', newline='', encoding='UTF-8') as myFile:
        reader = csv.reader(myFile)
        next(reader) 
        for row in reader:
            cardDict[row[0].lower()] = Card(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11])

    with open('output.csv', newline='', encoding='UTF-8') as myFile:
        reader = csv.reader(myFile)
        next(reader) 
        for row in reader:
            rulingDict[int(row[0])] = Ruling(row[0], row[1], row[2])
    
    url_list = []

    for i in range(1, bpCount + 1):
        if i < 10: 
            url_list.append("hbp0" + str(i))
        else:
            url_list.append("hbp" + str(i))
    for i in range(1, sdCount + 1):
        if i < 10: 
            url_list.append("hsd0" + str(i))
        else:
            url_list.append("hsd" + str(i))
    for i in range(1, ebCount + 1):
        if i < 10: 
            url_list.append("heb0" + str(i))
        else:
            url_list.append("heb" + str(i))
    url_list = url_list + ['ohc01', 'hys01', 'yell01', 'promo-100', 'promo-hbp10', 'promo-hsd10', 'promo-hbd20']

    for url in url_list:
        print("Checking", url)
        fullurl = "https://yuyu-tei.jp/sell/hocg/s/" + url
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(fullurl, headers=headers)
        res.encoding = res.apparent_encoding 
        soup = BeautifulSoup(res.text, "html.parser")

        mydivs = soup.find_all("div", {"class": "card-product"})

        for idx in range(len(mydivs)):
            setcode = mydivs[idx].find_all("span")[0].text
            rarity = mydivs[idx].find_all("img")[1].attrs['alt'].split()[1]
            priceString = mydivs[idx].find_all("strong")[0].text
            priceString = priceString.replace('\n', ' ').replace('\r', '')
            
            decimal_point_char = locale.localeconv()['decimal_point']
            clean = re.sub(r'[^0-9'+decimal_point_char+r']+', '', priceString)
            price = float(clean)

            imgurl = mydivs[idx].find_all("img")[1].attrs['src']
            
            if setcode.lower() not in cardDict:
                cardDict[setcode.lower()] = Card(setcode, "", "", "", rarity, "", "", "", "", "", "","")
            cardDict[setcode.lower()].addPrice(CardPrice(rarity, price, imgurl))
    
    groupList = []
    
    from urllib.request import Request
    url = "https://tcgcsv.com/tcgplayer/87/Groups.csv"
    req = Request('https://tcgcsv.com/tcgplayer/87/Groups.csv')
    req.add_header('User-Agent', 'HoloOCGBot/0.1.1')
    ftpstream = urllib.request.urlopen(req)
    csvfile = csv.reader(codecs.iterdecode(ftpstream, 'utf-8'))
    for line in csvfile:
        if line[0].isnumeric():
            groupList.append(line[0])

    for group in groupList:
        print("Checking group", group)
        url = "https://tcgcsv.com/tcgplayer/87/" + str(group) + "/ProductsAndPrices.csv"
        req = Request(url)
        req.add_header('User-Agent', 'HoloOCGBot/0.1.1')
        ftpstream = urllib.request.urlopen(req)
        csvfile = csv.reader(codecs.iterdecode(ftpstream, 'utf-8'))
        firstRow = True
        for line in csvfile:
            if firstRow:
                try:
                    setCodeIndex = line.index('extNumber')
                    rarityIndex = line.index('extRarity')
                    priceIndex = line.index('marketPrice')
                    fallbackIndex = line.index('midPrice')
                    urlIndex = line.index('imageUrl')
                    firstRow = False
                except:
                    break
            else:
                if len(line[setCodeIndex]) > 0:
                    if line[setCodeIndex].lower() not in cardDict:
                        cardDict[line[setCodeIndex].lower()] = Card(line[setCodeIndex], "", "", "", acronymize(line[rarityIndex]), "", "", "", "", "", "","")
                    if len(line[priceIndex]) > 0:
                        cardDict[line[setCodeIndex].lower()].addENPrice(CardPrice(acronymize(line[rarityIndex]), float(line[priceIndex]), line[urlIndex]))
                    elif len(line[fallbackIndex]) > 0:
                        cardDict[line[setCodeIndex].lower()].addENPrice(CardPrice(acronymize(line[rarityIndex]), float(line[fallbackIndex]), line[urlIndex]))
                    else:
                        cardDict[line[setCodeIndex].lower()].addENPrice(CardPrice(acronymize(line[rarityIndex]), None, line[urlIndex]))
                        
    import pandas as pd
    from datetime import datetime

    today = datetime.today()
    today_str = f"{today.month}/{today.day}/{today.year}"
    
    master_file = 'combined_prices.csv'
    id_cols = ['imgurl', 'Language', 'Setcode', 'Rarity']

    current_scrape_data = []
    for sc_lower, card_obj in cardDict.items():
        for rarity_key, price_obj in card_obj.priceDict.items():
            current_scrape_data.append({
                'imgurl': str(price_obj.url).strip(),
                'Language': 'JP',
                'Setcode': str(card_obj.setcode).strip().upper(),
                'Rarity': str(price_obj.rarity).strip().upper(),
                today_str: price_obj.price
            })
        for rarity_key, price_obj in card_obj.enPriceDict.items():
            current_scrape_data.append({
                'imgurl': str(price_obj.url).strip(),
                'Language': 'EN',
                'Setcode': str(card_obj.setcode).strip().upper(),
                'Rarity': str(price_obj.rarity).strip().upper(),
                today_str: price_obj.price
            })

    new_df = pd.DataFrame(current_scrape_data)

    if os.path.exists(master_file):
        master_df = pd.read_csv(master_file)
        
        def fix_col_format(col):
            if col in id_cols: return col
            if '-' in col:
                try:
                    dt = pd.to_datetime(col)
                    return f"{dt.month}/{dt.day}/{dt.year}"
                except: return col
            return col

        master_df.columns = [fix_col_format(c) for c in master_df.columns]
        master_df = master_df.T.groupby(level=0).first().T

        for col in ['Setcode', 'Rarity', 'Language']:
            master_df[col] = master_df[col].astype(str).str.strip().str.upper()
        master_df['imgurl'] = master_df['imgurl'].astype(str).str.strip()

        if today_str in master_df.columns:
            master_df = master_df.drop(columns=[today_str])

        new_df = new_df.groupby(id_cols).first().reset_index()
        master_df = pd.merge(master_df, new_df, on=id_cols, how='outer')
    else:
        master_df = new_df

    all_cols = master_df.columns.tolist()
    date_cols = [c for c in all_cols if c not in id_cols]

    def date_sort_key(date_str):
        try:
            m, d, y = map(int, date_str.split('/'))
            return (y, m, d)
        except:
            return (0, 0, 0) 

    date_cols.sort(key=date_sort_key)
    master_df = master_df[id_cols + date_cols]
    master_df.to_csv(master_file, index=False)
    
    global history_df
    history_df = master_df 
    
    print(f"Successfully updated {master_file} and sorted {len(date_cols)} dates.")

def textToColor(input):
    try:
        color = input.lower()
    except Exception as e:
        return discord.Colour.default()
    if color == 'white':
        return discord.Colour(0xE0E1E2)
    elif color == 'green':
        return discord.Colour.green()
    elif color == 'red':
        return discord.Colour.red()
    elif color == 'blue':
        return discord.Colour.blue()
    elif color == 'purple':
        return discord.Colour.purple()
    elif color == 'yellow':
        return discord.Colour.yellow()
    elif color == 'light_gray':
        return discord.Colour.green()
    else:
        return discord.Colour.default()

def getname(text):
    match = re.search(r'\((.*?)\)', text)
    if match:
        thing = re.sub(r"[^a-zA-Z0-9 +']", '', match.group(1)) 
        return thing
    return text

class ListPaginator(discord.ui.View):
    def __init__(self, invoker: discord.Member, pages: list, get_embed_func):
        super().__init__(timeout=120)
        self.invoker = invoker
        self.pages = pages
        self.get_embed = get_embed_func
        self.index = 0
        self.update_buttons()

    def update_buttons(self):
        self.button_prev.disabled = self.index == 0
        self.button_next.disabled = self.index == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.invoker

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji='◀️')
    async def button_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(self.index), view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji='▶️')
    async def button_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(self.index), view=self)


def cardEmbedMaker(input):
    card = cardDict[input.lower()]
    embed = discord.Embed(title=card.setcode, colour=textToColor(card.color))
    attText = ""
    attText += "**Name:** " + card.name +"\n"
    attText += "**Pack:** " + card.pack + "\n"
    attText += "**Rarity**: " + card.rarity + "\n"
    embed.add_field(name="Info", value=attText, inline=True)
    attText = ""
    attText += "**Type**: " + card.type + "\n"
    if len(card.color) > 0:
        attText += "**Color**: " + card.color + "\n"
    if card.rarity == "OSR" and len(card.life) > 0:
        attText += "**Life**: " + card.life + "\n"
    elif len(card.life) > 0:
        attText += "**HP**: " + card.life + "\n"
    if len(card.batonpass) > 0:
        attText += "**Baton Pass**: " + card.batonpass + "\n"
    if len(card.tags) > 0:
        attText += "**Tags**: " + card.tags + "\n"
    if len(card.metatags) > 0:
        attText += "**Meta Tags**: " + card.metatags + "\n"
    embed.add_field(name="Attributes", value=attText, inline=True)
    embed.add_field(name="Text", value=card.text, inline=False)
    try:
        embed.set_thumbnail(url="https://raw.githubusercontent.com/TurtleByte/holo-ocg-bot/refs/heads/main/images/" + card.setcode + ".png")
    except Exception as e:
        pass
    return embed

def getEmbed(arg, thumbnailurl=-1):
    card = cardDict[arg.lower()]
    pics = []
    embed = discord.Embed(title=card.setcode, colour=textToColor(card.color))
    embed.add_field(name="Name", value=card.name, inline=True)
    descText = ""
    lines = []
    for price in card.priceDict:
        priceObj = card.priceDict[price]
        lines.append(priceObj.rarity + " - ¥" + str(round(priceObj.price)) + " ($" + str(round(priceObj.price * 0.0067, 2)) + ")\n")
        pics.append(priceObj.url)
    lines.sort()
    for line in lines:
        descText += line
    embed.add_field(name="YYT Price (JP)", value=descText, inline=True)

    descText2 = ""
    lines = []
    for price in card.enPriceDict:
        priceObj = card.enPriceDict[price]
        if priceObj.price is not None:
            lines.append(priceObj.rarity + " - $" + str(round(priceObj.price, 2)) + "\n")
        else:
            lines.append(priceObj.rarity + " - [Unavailable]\n")
        pics.append(priceObj.url)
    lines.sort()
    for line in lines:
        descText2 += line
    embed.add_field(name="TCGPlayer Price (EN)", value=descText2, inline=True)
    embed.set_footer(text="Due to API limitations, prices are updated once a day.")

    if pics:
        embed.set_thumbnail(url=pics[thumbnailurl])
    return embed


class MainCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='card', description='Gets a card whether by name or setcode')
    async def getcard(self, interaction: discord.Interaction, query: str):
        if query.lower() in cardDict:
            await interaction.response.send_message(embed=cardEmbedMaker(query.lower()))
        else:
            candidates = []
            args = query.split()
            for keyword in args:
                candidatesbuffer = []
                for card in cardDict:
                    cardString = (cardDict[card].setcode + " " + getname(cardDict[card].name) + " " + cardDict[card].rarity + " " + cardDict[card].color + " " + cardDict[card].type + " " + cardDict[card].tags + " " + cardDict[card].metatags).lower()
                    cardString = re.sub(r"[^a-zA-Z0-9 +']", '', cardString) 
                    if keyword.lower() in cardString.split():
                        candidatesbuffer.append(cardDict[card].setcode)
                if len(candidatesbuffer) < 1:
                    for card in cardDict:
                        cardString = (cardDict[card].setcode + " " + getname(cardDict[card].name) + " " + cardDict[card].rarity + " " + cardDict[card].color + " " + cardDict[card].type + " " + cardDict[card].tags + " " + cardDict[card].metatags).lower()
                        if keyword.lower() in cardString:
                            candidatesbuffer.append(cardDict[card].setcode)
                if len(candidates) < 1:
                    candidates = candidatesbuffer.copy()
                else:
                    candidates = list(set(candidates) & set(candidatesbuffer))
            
            if len(candidates) == 1:
                card = cardDict[candidates[0].lower()]
                await interaction.response.send_message(embed=cardEmbedMaker(candidates[0].lower()))
            
            elif len(candidates) > 1:
                candidates.sort()
                
                # Split candidates into chunks of 15
                items_per_page = 15
                pages = [candidates[i:i + items_per_page] for i in range(0, len(candidates), items_per_page)]

                def get_page_embed(page_index):
                    descText = 'Multiple cards found. Did you mean any of the following?\n\n'
                    for candidate in pages[page_index]:
                        theCard = cardDict[candidate.lower()]
                        if 'holomem' in theCard.type:
                            descText += "**" + theCard.setcode + '** ' + getname(theCard.name) + ' ' + theCard.rarity + ' ' + theCard.type.replace('holomem', '') + '\n'
                        else:
                            descText += "**" + theCard.setcode + '** ' + getname(theCard.name) + ' ' + theCard.rarity + ' ' + theCard.type + '\n'
                    
                    embed = discord.Embed(title="Exact Card Not Found", colour=discord.Colour(0xff0000), description=descText)
                    embed.set_footer(text=f"Page {page_index + 1}/{len(pages)} | Please try again using the setcode.")
                    return embed

                # If there's more than one page, use the paginator view
                if len(pages) > 1:
                    view = ListPaginator(interaction.user, pages, get_page_embed)
                    await interaction.response.send_message(embed=get_page_embed(0), view=view)
                else:
                    await interaction.response.send_message(embed=get_page_embed(0))
            else:
                embed = discord.Embed(title="Card Not Found", colour=discord.Colour(0xff0000), description="Please check the Setcode or Name.")
                await interaction.response.send_message(embed=embed)

    @app_commands.command(name='qna', description='Gets a ruling or Q&A entry')
    async def qna(self, interaction: discord.Interaction, query: str):
        if query.isnumeric():
            if int(query) in rulingDict:
                ruling = rulingDict[int(query)]
                embed = discord.Embed(title='Q&A ' + str(int(query)))
                embed.add_field(name="Question", value=ruling.question, inline=True)
                embed.add_field(name="Answer", value=ruling.answer, inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("Q&A Number not found.", ephemeral=True)
        else:
            candidates = []
            args = query.split()
            for keyword in args:
                candidatesbuffer = []
                for ruling in rulingDict:
                    if keyword.lower() in rulingDict[ruling].question.lower():
                        candidatesbuffer.append(ruling)
                if len(candidates) < 1:
                    candidates = candidatesbuffer.copy()
                else:
                    candidates = list(set(candidates) & set(candidatesbuffer))
            candidates.sort()
            
            if len(candidates) == 1:
                ruling = rulingDict[candidates[0]]
                embed = discord.Embed(title='Q&A ' + str(candidates[0]))
                embed.add_field(name="Question", value=ruling.question, inline=True)
                embed.add_field(name="Answer", value=ruling.answer, inline=True)
                await interaction.response.send_message(embed=embed)
            
            elif len(candidates) > 1:
                # Split candidates into chunks of 15
                items_per_page = 15
                pages = [candidates[i:i + items_per_page] for i in range(0, len(candidates), items_per_page)]

                def get_page_embed(page_index):
                    descText = 'Multiple instances found. Did you mean any of the following?\n\n'
                    for candidate in pages[page_index]:
                        result = rulingDict[candidate]
                        descText += "**" + str(candidate) + "**: " + result.question + "\n"
                    
                    # Failsafe: Discord has a 4096 character limit for descriptions
                    if len(descText) > 4000:
                        descText = descText[:4000] + "...\n**(Truncated due to Discord length limits)**"

                    embed = discord.Embed(title="Q&A Search", colour=discord.Colour(0xff0000), description=descText)
                    embed.set_footer(text=f"Page {page_index + 1}/{len(pages)} | Please try again using the Number.")
                    return embed

                # If there's more than one page, use the paginator view
                if len(pages) > 1:
                    view = ListPaginator(interaction.user, pages, get_page_embed)
                    await interaction.response.send_message(embed=get_page_embed(0), view=view)
                else:
                    await interaction.response.send_message(embed=get_page_embed(0))
            else:
                embed = discord.Embed(title="Nothing Found", colour=discord.Colour(0xff0000), description="Please check the input.")
                await interaction.response.send_message(embed=embed)

    @app_commands.command(name='price', description='Gets Yuyutei/TCGPlayer price by setcode')
    async def getprice(self, interaction: discord.Interaction, query: str):
        if query.lower() in cardDict:
            class Buttons(discord.ui.View):
                def __init__(self, invoker, *, timeout=30):
                    super().__init__(timeout=timeout)
                    self.invoker = invoker
                    self.index = -1
                async def interaction_check(self, button_interaction: discord.Interaction) -> bool:
                    return button_interaction.user == self.invoker
                @discord.ui.button(style=discord.ButtonStyle.gray, emoji='◀️')
                async def button_A(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.index -= 1
                    await button_interaction.response.edit_message(embed=getEmbed(query, self.index), view=self)
                @discord.ui.button(style=discord.ButtonStyle.gray, emoji='▶️')
                async def button_B(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.index += 1
                    await button_interaction.response.edit_message(embed=getEmbed(query, self.index), view=self)

            embed = getEmbed(query)
            view = Buttons(interaction.user)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            candidates = []
            args = query.split()
            for keyword in args:
                candidatesbuffer = []
                for card in cardDict:
                    cardString = (cardDict[card].setcode + " " + getname(cardDict[card].name) + " " + cardDict[card].rarity + " " + cardDict[card].color + " " + cardDict[card].type + " " + cardDict[card].tags + " " + cardDict[card].metatags).lower()
                    cardString = re.sub(r"[^a-zA-Z0-9 +']", '', cardString) 
                    if keyword.lower() in cardString.split():
                        candidatesbuffer.append(cardDict[card].setcode)
                if len(candidatesbuffer) < 1:
                    for card in cardDict:
                        cardString = (cardDict[card].setcode + " " + getname(cardDict[card].name) + " " + cardDict[card].rarity + " " + cardDict[card].color + " " + cardDict[card].type + " " + cardDict[card].tags + " " + cardDict[card].metatags).lower()
                        if keyword.lower() in cardString:
                            candidatesbuffer.append(cardDict[card].setcode)
                if len(candidates) < 1:
                    candidates = candidatesbuffer.copy()
                else:
                    candidates = list(set(candidates) & set(candidatesbuffer))

            if len(candidates) == 1:
                embed = getEmbed(candidates[0].lower())
                class Buttons(discord.ui.View):
                    def __init__(self, invoker, *, timeout=30):
                        super().__init__(timeout=timeout)
                        self.invoker = invoker
                        self.index = -1
                    async def interaction_check(self, button_interaction: discord.Interaction) -> bool:
                        return button_interaction.user == self.invoker
                    @discord.ui.button(style=discord.ButtonStyle.gray, emoji='◀️')
                    async def button_A(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        self.index -= 1
                        await button_interaction.response.edit_message(embed=getEmbed(candidates[0], self.index), view=self)
                    @discord.ui.button(style=discord.ButtonStyle.gray, emoji='▶️')
                    async def button_B(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        self.index += 1
                        await button_interaction.response.edit_message(embed=getEmbed(candidates[0], self.index), view=self)
                view = Buttons(interaction.user)
                await interaction.response.send_message(embed=embed, view=view)
            
            elif len(candidates) > 1:
                candidates.sort()
                
                # Split candidates into chunks of 15
                items_per_page = 15
                pages = [candidates[i:i + items_per_page] for i in range(0, len(candidates), items_per_page)]

                def get_page_embed(page_index):
                    descText = 'Multiple cards found. Did you mean any of the following?\n\n'
                    for candidate in pages[page_index]:
                        theCard = cardDict[candidate.lower()]
                        if 'holomem' in theCard.type:
                            descText += "**" + theCard.setcode + '** ' + getname(theCard.name) + ' ' + theCard.rarity + ' ' + theCard.type.replace('holomem', '') + '\n'
                        else:
                            descText += "**" + theCard.setcode + '** ' + getname(theCard.name) + ' ' + theCard.rarity + ' ' + theCard.type + '\n'
                    
                    embed = discord.Embed(title="Exact Card Not Found", colour=discord.Colour(0xff0000), description=descText)
                    embed.set_footer(text=f"Page {page_index + 1}/{len(pages)} | Please try again using the setcode.")
                    return embed

                # If there's more than one page, use the paginator view
                if len(pages) > 1:
                    view = ListPaginator(interaction.user, pages, get_page_embed)
                    await interaction.response.send_message(embed=get_page_embed(0), view=view)
                else:
                    await interaction.response.send_message(embed=get_page_embed(0))
            else:
                embed = discord.Embed(title="Card Not Found", colour=discord.Colour(0xff0000), description="Please check the Setcode or Name.")
                await interaction.response.send_message(embed=embed)


    # Define the autocomplete callback for rarity
    async def rarity_autocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        global history_df
        rarities = set()

        # Try to get unique rarities from the history DataFrame first
        if not history_df.empty and 'Rarity' in history_df.columns:
            rarities = set(history_df['Rarity'].dropna().astype(str).unique())
        else:
            # Fallback: scan through the cardDict if history_df hasn't been loaded yet
            for card in cardDict.values():
                for price_obj in card.priceDict.values():
                    if price_obj.rarity:
                        rarities.add(str(price_obj.rarity).upper())
                for price_obj in card.enPriceDict.values():
                    if price_obj.rarity:
                        rarities.add(str(price_obj.rarity).upper())

        # Filter out blanks and match against what the user is currently typing
        valid_rarities = [r.strip() for r in rarities if r.strip()]
        matches = [r for r in valid_rarities if current.lower() in r.lower()]
        
        # Discord allows a maximum of 25 autocomplete choices
        return [app_commands.Choice(name=r, value=r) for r in matches[:25]]

    @app_commands.command(name='pricehistory', description='View price history for a specific card')
    @app_commands.describe(
        setcode="The set code of the card (e.g. hbp01-001)",
        language="Language of the card",
        rarity="Rarity of the card"
    )
    @app_commands.choices(language=[
        app_commands.Choice(name='JP', value='jp'),
        app_commands.Choice(name='EN', value='en')
    ])
    @app_commands.autocomplete(rarity=rarity_autocomplete)
    async def pricehistory(self, interaction: discord.Interaction, setcode: str, language: app_commands.Choice[str], rarity: str):
        global history_df

        argSetcode = setcode.lower()
        argLanguage = language.value # Extract the value from the Choice object
        argRarity = rarity.lower()

        if history_df.empty:
            if os.path.exists('combined_prices.csv'):
                history_df = pd.read_csv('combined_prices.csv')
            else:
                await interaction.response.send_message("History data not found. Please run a scrape first.", ephemeral=True)
                return

        mask = (
            (history_df['Setcode'].str.lower() == argSetcode) &
            (history_df['Language'].str.lower() == argLanguage) &
            (history_df['Rarity'].str.lower() == argRarity)
        )
        results = history_df[mask]

        if results.empty:
            await interaction.response.send_message("No history found for that specific card, language, and rarity combination.", ephemeral=True)
            return

        row = results.iloc[0]

        card = cardDict.get(argSetcode)
        color = textToColor(card.color) if card else discord.Colour.default()
        
        embed = discord.Embed(
            title=f"Price History: {card.name if card else argSetcode.upper()}",
            colour=color
        )

        embed.add_field(
            name=f"Info", 
            value=f"**Setcode:** {argSetcode.upper()}\n**Lang:** {argLanguage.upper()}\n**Rarity:** {row['Rarity'].upper()}", 
            inline=True
        )

        if pd.notna(row['imgurl']):
            embed.set_thumbnail(url=str(row['imgurl']))

        id_cols = ['imgurl', 'Language', 'Setcode', 'Rarity']
        date_cols = [c for c in history_df.columns if c not in id_cols]
        
        changes = []
        last_price = None
        
        for date in date_cols:
            current_price = row[date]
            if pd.notna(current_price) and current_price != last_price:
                changes.append((date, current_price))
                last_price = current_price
        
        display_data = changes[-8:] if len(changes) > 8 else changes
        
        history_lines = []
        symbol = "¥" if argLanguage == "jp" else "$"
        
        for date, price in display_data:
            if argLanguage == "jp":
                p_val = f"{int(float(price)):,}"
            else:
                p_val = f"{float(price):.2f}"
            history_lines.append(f"`{date}`: **{symbol}{p_val}**")

        embed.add_field(
            name=f"Price Changes (Latest {len(display_data)})", 
            value="\n".join(history_lines) if history_lines else "No price changes recorded.", 
            inline=True
        )
        
        if len(changes) > 8:
            embed.set_footer(text=f"Displaying 8 of {len(changes)} total recorded price movements.")

        await interaction.response.send_message(embed=embed)

@bot.command(name='getcard', help='gets a card whether by name or setcode', aliases=['card'])
async def getcard(ctx):
    await ctx.send(content="All commands have been moved to Slash Commands! Make sure they're enabled on your server to use them!")

@bot.command(name='qna', help='gets a ruling or Q&A entry', aliases=['faq', 'ruling'])
async def qna(ctx):
    await ctx.send(content="All commands have been moved to Slash Commands! Make sure they're enabled on your server to use them!")
    
@bot.command(name='getprice', help='gets YYT price by setcode', aliases=['price'])
async def getprice(ctx):
    await ctx.send(content="All commands have been moved to Slash Commands! Make sure they're enabled on your server to use them!")

@bot.command(name='pricehistory', help='format: !history setcode language rarity', aliases=['history'])
async def pricehistory(ctx):
    await ctx.send(content="All commands have been moved to Slash Commands! Make sure they're enabled on your server to use them!")


@bot.command(name='sync',
             help='Syncs commands.',
             aliases=[],
             extras={
                 'format': 'sync',
                 'parameters': [],
                 'examples': [],
                 'tags': ['Mod Only']
             })
@commands.guild_only()
@commands.is_owner()
async def sync(
  ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: typing.Optional[typing.Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()
        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return
    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1
    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: discord.app_commands.Command):
    print(f"{interaction.user.name} ({interaction.user.id}) in {interaction.channel_id} ran /{command.name}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    return

bot.run(TOKEN)