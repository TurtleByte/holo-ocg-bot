import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import csv

# discord token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# sets Intents (why do i have to do this)
intents = discord.Intents.all()

# defining the bot
bot = commands.Bot(case_insensitive=True, command_prefix='!', help_command = None, intents=intents)

# Event: when bot is ready
@bot.event
async def on_ready():
    startupRoutine()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

class Card:
    def __init__(self, setcode, name, image, type, rarity, color, life, tags, text):
        self.setcode = setcode
        self.name = name
        self.image = image
        self.type = type
        self.rarity = rarity
        self.color = color
        self.life = life
        self.tags = tags
        self.text = text

cardDict = {}

def startupRoutine():
    global cardDict
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = [f for f in os.listdir(script_dir) if f.lower().endswith('.csv')]
    for cardlist in csv_files:
        print("Ingesting", cardlist)
        with open(cardlist, newline='', encoding='UTF-8') as myFile:
            reader = csv.reader(myFile)
            next(reader) # skips header
            for row in reader:
                cardDict[row[0].lower()] = Card(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
            myFile.close()

def textToColor(input):
    color = input.lower()
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

# Basic command: ping
@bot.command(name='getcard', help='gets a card whether by name or setcode', aliases=['card'])
async def getcard(ctx, arg):
    if arg.lower() in cardDict:
        card = cardDict[arg.lower()]
        embed = discord.Embed(title=card.setcode, colour=textToColor(card.color))
        embed.add_field(name="Name", value=card.name, inline=True)
        embed.add_field(name="Type", value=card.type, inline=True)
        embed.add_field(name="Rarity", value=card.rarity, inline=True)
        embed.add_field(name="Color", value=card.color, inline=True)
        embed.add_field(name="Life/HP", value=card.life, inline=True)
        embed.add_field(name="Tags", value=card.tags, inline=True)
        embed.add_field(name="Text", value=card.text, inline=False)

        imageurl = "images/" + card.setcode + ".png"
        imagename = card.setcode + ".png"
        file = discord.File(imageurl, filename=imagename)  
        # embed.set_image(url='attachment://' + imagename)
        embed.set_thumbnail(url='attachment://' + imagename)
        await ctx.send(content="", file=file, embed=embed)
    else:
        candidates = []
        for card in cardDict:
            if arg.lower() in cardDict[card].name.lower():
                candidates.append(cardDict[card].setcode)
        if len(candidates) == 1:
            await getcard(ctx, candidates[0])
        elif len(candidates) > 1:
            descText = 'Multiple cards found. Did you mean any of the following?\n\n'
            for candidate in candidates:
                theCard = cardDict[candidate.lower()]
                descText += theCard.setcode + ' ' + ''.join(theCard.name.splitlines()) + ' ' + theCard.rarity + '\n' 
            embed = discord.Embed(title="Exact Card Not Found", colour=discord.Colour(0xff0000), description=descText)
            embed.set_footer(text="Please try again using the setcode.")
            await ctx.send(content="", embed=embed)
        else:
            embed = discord.Embed(title="Card Not Found", colour=discord.Colour(0xff0000), description="Please check the Setcode or Name.")
            await ctx.send(content="", embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        return
    raise error

bot.run(TOKEN)