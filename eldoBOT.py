import os
from time import sleep
import time
import discord
from discord import NotFound
from dotenv import load_dotenv
import requests #dependency
import json
from PIL import Image
from io import BytesIO
import io
import random
import re
import mysql.connector
import emoji
import unicodedata
from unidecode import unidecode
from collections import Counter
import operator
import pickle
import cv2
from tracemoe import TraceMoe

# Get configurations
configurations = pickle.load(open("configurations.pkl", "rb" ))
activator = "e!"

# Get some secrets from the magic Pickle
keys = pickle.load(open("keys.pkl", "rb" ))

 ## Connect to Database
mydb = mysql.connector.connect(
     host=keys["Database"]["host"],
     user=keys["Database"]["user"],
     passwd=keys["Database"]["passwd"],
     database=keys["Database"]["database"])
mycursor = mydb.cursor()

Discord_TOKEN = keys["Discord_TOKEN"]
sauceNAO_TOKEN = keys["sauceNAO_TOKEN"]

# Initialize client
client = discord.Client()
try:
    anon_list = pickle.load(open("anon_list.pkl", "rb" ))
    print("Pickle file loaded")
except:
    print("Error, couldn't load Pickle File")
    anon_list = {}

channel_logs=0

# Notes:
# Hey!! Add https://soruly.github.io/trace.moe/#/ to your bot! It has an easy to use API, and nice limits
# It also gives you information when the saucenao doesn't.

# Don't allow mentions of any type
##allowed_mentions_NONE = discord.AllowedMentions(everyone=False, users=False, roles=False)

async def get_video_frame(attachment):
    with open("temp.mp4", 'wb') as video_file:
        video_file = await attachment.save(video_file)
    cam = cv2.VideoCapture("temp.mp4")
    ret,image_to_search = cam.read()
    print(type(image_to_search),type(ret),type(cam),type(video_file))
    return image_to_search

async def find_name(msg):
    # Check if we can send names to this channel
    can_i_send_message = False
    if "name_channel" in configurations["guilds"][msg.guild.id]["commands"]:
        if configurations["guilds"][msg.guild.id]["commands"]["name_channel_set"] == True:
            if msg.channel.id in configurations["guilds"][msg.guild.id]["commands"]["name_channel"]:
                can_i_send_message = True
            else:
                can_i_send_message = False
        else: # If the user didn't configured the allowed channels, we will just send the command
            can_i_send_message = True
    else:
        can_i_send_message = True

    # If the user sent the command in a channel where we don't allow it
    if can_i_send_message == False:
        return configurations["guilds"][msg.guild.id]["commands"]["name_ignore_message"]+"TEMP_MESSAGE"

    if len(msg.attachments)==0:
        return("❌")

    image_to_search_URL = msg.attachments[0].url
    if msg.attachments[0].filename.find(".mp4")!=-1:
        image_to_search = await get_video_frame(msg.attachments[0])
        image_to_search = Image.fromarray(image_to_search, 'RGB')
    else:
        image_to_search = requests.get(image_to_search_URL)
        image_to_search = Image.open(BytesIO(image_to_search.content))
    print("Searching image: "+image_to_search_URL)

    image_to_search = image_to_search.convert('RGB')
    image_to_search.thumbnail((250,250), resample=Image.ANTIALIAS)
    imageData = io.BytesIO()
    image_to_search.save(imageData,format='PNG')
    text_ready = False

    # Original URL (For future changes)
    # url = 'http://saucenao.com/search.php?output_type=2&numres=1&minsim='+minsim+'&dbmask='+str(db_bitmask)+'&api_key='+api_key
    url = 'http://saucenao.com/search.php?output_type=2&numres=1&minsim=85!&dbmask=79725015039&api_key='+sauceNAO_TOKEN
    files = {'file': ("image.png", imageData.getvalue())}
    imageData.close()
    r = requests.post(url, files=files)
    if r.status_code != 200:
        if r.status_code == 403:
            print('Incorrect or Invalid API Key! Please Edit Script to Configure...')
        else:
            #generally non 200 statuses are due to either overloaded servers or the user is out of searches
            print("status code: "+str(r.status_code))
            msg.add_reaction("🕖")
    else:
        results = json.loads(r.text)
        result_data = results["results"][0]["data"]
        similarity_of_result = results["results"][0]["header"]["similarity"]

        if float(similarity_of_result)>85:
            message_with_source = "Estoy " + str(similarity_of_result) +"\% seguro de que la imagen"
        elif float(similarity_of_result)>65:
            message_with_source = "Probablemente la imagen"
        else:
            message_with_source = "Puede que la imagen"
        if(float(similarity_of_result)>58):
            if "pixiv_id" in result_data:
                message_with_source += " es del artista **"+result_data["member_name"]+"**"
                if requests.get(result_data["ext_urls"][0]).status_code != 404:
                    message_with_source += ", y el link a su página de Pixiv es este:\n<" + result_data["ext_urls"][0] + ">"
                else:
                    message_with_source += ", y su cuenta de Pixiv fué eliminada, así que no puedo darte más información"
                text_ready = True
            elif "nijie_id" in result_data:
                message_with_source += " es del artista **"+ result_data["member_name"]+"** y tiene como título *" + result_data["title"]+"* (si esta info no te sirve, haz click aquí: <"+result_data["ext_urls"][0]+">)"
                text_ready = True
            elif "source" in result_data and not text_ready:
                if "part" in result_data:
                    message_with_source += " es del anime **" + result_data["source"]
                    message_with_source += "**, episodio " + result_data["part"]
                    text_ready = True

                elif result_data["source"].find("twitter.com")!=-1:
                    message_with_source += " es del artista **"+result_data["creator"] + "**, "
                    if "material" in result_data:
                        message_with_source += "inspirado en el anime *"+result_data["material"]
                    if requests.get(result_data["source"]).status_code != 404:
                        message_with_source += "* y el link al Twitt original es este:\n"
                        message_with_source += result_data["source"]
                    else:
                        message_with_source += "* y el link al Twitt original está caído."
                    text_ready = True

                elif "sankaku_id" in result_data or "gelbooru_id" in result_data:
                    if "creator" in result_data:
                        if result_data["creator"] == "":
                            print(result_data["material"])
                            if result_data["material"] != "":
                                message_with_source += " es del anime **" + result_data["material"][0:result_data["material"].find(",")]+"**"
                                if result_data["characters"] != "":
                                    if result_data["characters"].find(",") == -1:
                                        message_with_source += " y el personaje es *" + result_data["characters"]+"*"
                                    else:
                                        message_with_source += " y el personaje es *" + result_data["characters"][0:result_data["characters"].find(",")]+"*"
                                    text_ready = True
                    if "material" in result_data and not text_ready:
                        if result_data["material"]=="original":
                            message_with_source += " es un personaje original"
                            if "characters" in result_data:
                                if result_data["characters"]!="":
                                    message_with_source += " llamado *" + result_data["characters"] + "* y"
                                else:
                                    message_with_source += " y"
                            else:
                                message_with_source += " y"
                        elif result_data["material"]!="":
                            message_with_source += " es de un anime llamado **" + result_data["material"] + "** y"
                    message_with_source += " es del artista **"+result_data["creator"] + "**"
                    text_ready = True
            elif "getchu_id" in result_data:
                message_with_source += " es de la comapnía de videojuegos *" + result_data["company"]+"* "
                message_with_source += "y el juego se llama **" + result_data["title"] + "**"
                text_ready = True
            else:
                print("Encontramos fuente, pero no supimos como mostrarla. Link de la imagen:"+image_to_search_URL+"\n")
                print("Array obtenido: "+str(result_data))

        if text_ready:
            return message_with_source
        else:
            #tracemoe = TraceMoe()
            #response = await tracemoe.search(
            #    image_to_search_URL,
            #    is_url=True
            #)
            #video = await tracemoe.video_preview_natural(response)
            #discord_video = Discord.File(fp = BytesIO(video))


            return "❌"
@client.event
async def on_guild_join(guild):
    msg_to_send = "Fuimos invitados a un nuevo servidor!! Nombre:", guild.name
    print(msg_to_send)
    await channel_logs.send(msg_to_send)
    if not guild.id in configurations["guilds"]:
        configurations["guilds"][guild.id] = {"general":{},"commands":{"name_channel_set":False,"name_channel":[],"name_ignore_message":""},"others":{}}
        with open("configurations.pkl", 'wb') as pickle_file:
            pickle.dump(configurations,pickle_file)

@client.event
async def on_ready():
    global channel_logs
    print(f'{client.user.name} has connected to Discord!')
    # Get channel for logs:
    channel_logs = await client.fetch_channel(708648213774598164)

@client.event
async def on_raw_reaction_add(payload):
    if(str(payload.emoji) == "🔍" or str(payload.emoji) == "🔎"):
        channel = client.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)
        async with channel.typing():
            msg_to_send = await find_name(msg)
        if msg_to_send.find("TEMP_MESSAGE")!=-1:
            await msg.channel.send(content=msg_to_send.replace("TEMP_MESSAGE",""), delete_after=60)
        elif(msg_to_send != "❌"):
            #img_to_send = await msg.attachments[0].read()
            #img_to_send = discord.File(img_to_send,filename="sauce.jpg")
            await msg.channel.send(msg_to_send)#,file=img_to_send)
        else:
            await msg.add_reaction("❌")

@client.event
async def on_message(msg):
    global channel_logs

    # Ignore messages comming from a bot
    if msg.author.bot:
        return

    async def command_help():
        help_text = "**Comandos de EldoBOT:**\n"
        help_text += "**{}say [mensaje]**:\n".format(activator) # 'format(activator)"' Puts the "e!" on the help
        help_text += "Has que el bot diga algo.\n"
        help_text += "**{}di como [@usuario] [mensaje]**:\n".format(activator)
        help_text += "El bot imitará al @usuario y enviará lo escrito en *mensaje*.\n"
        help_text += "**{}bot [mensaje]**:\n".format(activator)
        help_text += "El bot te imitará y enviará lo escrito en *mensaje*.\n"
        help_text += "**{}anon [confesión]**:\n".format(activator)
        help_text += "Este comando es para enviar una confesión en el canal de confesiónes.\n"
        help_text += "**name o nombre**:\n"
        help_text += "El bot buscará el nombre de la imagen adjunta al mensaje.\n"
        help_text += "**spoiler**:\n"
        help_text += "El bot imitará al usuario y reenviará las imagenes como spoilers.\n"
        help_text += "**{}test_stats**:\n".format(activator)
        help_text += "El bot mostrará el uso de los emojis en el servidor. *En construcción*\n"
        help_text += "**{}emoji_stats [@usuario]**:\n".format(activator)
        help_text += "El bot mostrará el uso de emojis del usuario. *En construcción*\n"
        help_text += "**{}boost list**:\n".format(activator)
        help_text += "El bot devuelve una lista con los usuarios que boostean el servidor.\n"
        await msg.channel.send(help_text)

    async def command_config():
        if msg.author.permissions_in(msg.channel).manage_channels:
            if msg.content.find("e!conf name ignore_message ")==0:
                name_ignore_message = msg.content.replace("e!conf name ignore_message ","")
                configurations["guilds"][msg.guild.id]["commands"]["name_ignore_message"] = name_ignore_message
                with open("configurations.pkl", 'wb') as pickle_file:
                    pickle.dump(configurations,pickle_file)
                await msg.channel.send(content="Mensaje cambiado correctamente",delete_after=3)
        else:
            await msg.channel.send(content="No tienes permisos suficientes para hacer esto",delete_after=3)

    async def command_config_permName():
        if msg.author.permissions_in(msg.channel).manage_channels:
            configurations["guilds"][msg.guild.id]["commands"]["name_channel_set"] = True
            configurations["guilds"][msg.guild.id]["commands"]["name_channel"].append(msg.channel.id)
            with open("configurations.pkl", 'wb') as pickle_file:
                pickle.dump(configurations,pickle_file)
            await msg.channel.send(content="Ahora se podrá usar el comando **name** en este canal",delete_after=3)
        else:
            await msg.channel.send(content="No tienes permisos suficientes para hacer esto",delete_after=3)

    async def command_config_bloqName():
        if msg.author.permissions_in(msg.channel).manage_channels:
            if msg.channel.id in configurations["guilds"][msg.guild.id]["commands"]["name_channel"]:
                del(configurations["guilds"][msg.guild.id]["commands"]["name_channel"][msg.channel.id])
                with open("configurations.pkl", 'wb') as pickle_file:
                    pickle.dump(configurations,pickle_file)
            await msg.channel.send(content="Ya no se podrá usar el comando **name** en este canal",delete_after=3)
        else:
            await msg.channel.send(content="No tienes permisos suficientes para hacer esto",delete_after=3)

    async def command_say():
        text_to_say = msg.clean_content
        text_to_say = text_to_say.replace("e!say","",1)
        text_to_say = text_to_say.replace("e!di","",1)

        # temp solution
        text_to_say = text_to_say.replace("@everyone","every**nyan**")
        text_to_say = text_to_say.replace("@here","nope")

        embed_to_send = discord.Embed(description=text_to_say, colour=16761856).set_footer(text="Enviado por: " + msg.author.display_name)

        await msg.channel.send(embed = embed_to_send)
        await msg.delete()

    async def debugTraceMoe():
        if len(msg.attachments)>0:
            image_to_search_URL = msg.attachments[0].url
        else:
            return
        tracemoe = TraceMoe()

        fileToSend = None

        async with msg.channel.typing():
            response = tracemoe.search(
                image_to_search_URL,
                is_url=True
            )
            try:
                videoN = tracemoe.video_preview_natural(response)
                fileToSend = discord.File(fp = BytesIO(videoN),filename="preview.mp4")
            except:
                pass
                image = tracemoe.image_preview(response)
                fileToSend = discord.File(fp = BytesIO(image),filename="preview.jpg")

            # Detect type of Anime
            if "is_adult" in response["docs"][0]:
                if(response["docs"][0]["is_adult"]==True):
                    typeOfAnime = "H"
            else:
                typeOfAnime = "anime"

            # Get Anime tittle
            if "title_english" in response["docs"][0]:
                if response["docs"][0]["title_english"]!="":
                    nameOfAnime = response["docs"][0]["title_english"]
            else:
                nameOfAnime = response["docs"][0]["anime"]

            # Get Anime episode
            if "episode" in response["docs"][0]:
                if response["docs"][0]["episode"]!=None:
                    episodeOfAnime = str(response["docs"][0]["episode"])
            else:
                episodeOfAnime = "cuyo número no recuerdo"

            # Get Anime season (year)
            if "season" in response["docs"][0]:
                if response["docs"][0]["season"]!=None:
                    seasonOfAnime = str(response["docs"][0]["season"])
            else:
                seasonOfAnime = "en el que se produjo"

            # Get simmilarity
            if "similarity" in response["docs"][0]:
                if response["docs"][0]["similarity"]!=None:
                    simmilarityOfAnime = "{:04.2f}".format(response["docs"][0]["similarity"]*100.0)
            else:
                print("similarity Not Found")
                print(response)
                return

            msg_to_send = "Estoy {} seguro de que la imágen es de un {} del año {} llamado **\"{}\"** , episodio {}.".format(simmilarityOfAnime,typeOfAnime,seasonOfAnime,nameOfAnime,episodeOfAnime)

            await msg.channel.send(content = msg_to_send,file = fileToSend)

    async def testTraceMoe():
        if len(msg.attachments)>0:
            image_to_search_URL = msg.attachments[0].url
        tracemoe = TraceMoe()
        async with msg.channel.typing():
            response = tracemoe.search(
                image_to_search_URL,
                is_url=True
            )
            video = tracemoe.video_preview_natural(response)
            msg_to_send = ""
            msg_to_send += "Estoy "+str(response["docs"][0]["similarity"])+"\% seguro de que la imágen es del anime **"+response["docs"][0][0]["title_english"]
            msg_to_send += "** del episodio "+str(response["docs"][0]["episode"])

            discord_video = discord.File(fp = BytesIO(video),filename="preview.mp4")
            await msg.channel.send(content = msg_to_send,file = discord_video)


    async def command_guilds():
        msg_to_say = ""
        for guild in client.guilds:
            msg_to_say+=guild.name + "\n"
        await msg.channel.send(msg_to_say)

    async def command_spoiler():
        if len(msg.attachments)>0:
            tmp_list_images=[]
            for attachment in msg.attachments:
                tmp_img_bytes = await attachment.read()
                tmp_img_filename = attachment.filename
                tmp_img_bytes = BytesIO(tmp_img_bytes)
                tmp_img = discord.File(tmp_img_bytes, spoiler=True, filename=tmp_img_filename)
                tmp_list_images.append(tmp_img)

            pfp_to_imitate = await msg.author.avatar_url.read()
            # Create Webhook
            webhook_discord = await msg.channel.create_webhook(name=msg.author.display_name, avatar=pfp_to_imitate, reason="EldoBOT: Temp-webhook")
            # Send message
            await webhook_discord.send(content=msg.content, files = tmp_list_images, username = msg.author.display_name)#, allowed_mentions = allowed_mentions_NONE)
            print("Spoiler printed!")
            # Delete webhook
            await webhook_discord.delete()
            await msg.delete()


    async def command_ping():
        await msg.channel.send("pong")

    async def command_emoji_stats():
        if msg.content == ("e!emoji_stats yo"):
            user_to_search = msg.author.id
        elif msg.content.find("e!emoji_stats id: ")==0:
            user_to_search = int(msg.content.replace("e!emoji_stats id: ",""))
        elif len(msg.raw_mentions)>0:
            user_to_search = msg.raw_mentions[0]
        else:
            searchAll()
            return

        mySQL_call = ("SELECT emoji.emoji_id, emoji.call_name ")
        mySQL_call += ("FROM HelloWorld.emoji_log ")
        mySQL_call += ("INNER JOIN HelloWorld.emoji ON emoji_log.emoji = emoji.emoji_id ")
        mySQL_call += ("WHERE emoji_log.user =" + str(user_to_search))
        mycursor.execute(mySQL_call)
        tmp_list_of_emojis = mycursor.fetchall()

        list_of_emojis=[]
        for element in tmp_list_of_emojis:
            list_of_emojis.append(element[0])
        dic_with_repetitions = Counter(list_of_emojis)
        mensaje_a_mostrar = "Aquí una lista (Función en construcción):\n"

        # Sort Dictionary and save in Tuples
        sorted_list_emojis = sorted(dic_with_repetitions.items(), key=operator.itemgetter(1), reverse=True)
        for emoji_id, times_repeated in sorted_list_emojis:
            # Normie Emoticons😂 <- Puajj
            if len(emoji_id) < 18:
                if(len(mensaje_a_mostrar)>=1950):
                    await msg.channel.send(mensaje_a_mostrar)
                    mensaje_a_mostrar = ""
                mensaje_a_mostrar += chr(int(emoji_id)) + " -> " + str(times_repeated) + " | "

            # Discord Emotes :doge: <- Nice :3
            else:
                emote = client.get_emoji(int(emoji_id))
                if(emote!=None):
                    mensaje_a_mostrar += "<:" + emote.name + ":" + str(emote.id) + "> -> " + str(times_repeated) + " | "
        await msg.channel.send(mensaje_a_mostrar)

        async def searchAll():
            print("Looking for stats data...")
            mycursor.execute("SELECT emoji FROM emoji_log WHERE guildID='624079272155414528';")
            tmp_list_of_emojis = mycursor.fetchall()
            list_of_emojis=[]
            for element in tmp_list_of_emojis:
                list_of_emojis.append(element[0])
            dic_with_repetitions = Counter(list_of_emojis)
            mensaje_a_mostrar = "Aquí una lista (Función en construcción):\n"

            # Sort Dictionary and save in Tuples
            sorted_list_emojis = sorted(dic_with_repetitions.items(), key=operator.itemgetter(1), reverse=True)
            for emoji_id, times_repeated in sorted_list_emojis:
                # Normie Emoticons😂 <- Puajj
                if len(emoji_id) < 18:
                    #print(mensaje_a_mostrar)
                    if(len(mensaje_a_mostrar)>=1800):
                        await msg.channel.send(mensaje_a_mostrar)
                        mensaje_a_mostrar = ""
                    mensaje_a_mostrar += chr(int(emoji_id)) + " -> " + str(times_repeated) + " | "

                # Discord Emotes :doge: <- Nice :3
                else:
                    emote = client.get_emoji(int(emoji_id))
                    if(emote!=None):
                        mensaje_a_mostrar += "<:" + emote.name + ":" + str(emote.id) + "> -> " + str(times_repeated) + " | "
            await msg.channel.send(mensaje_a_mostrar)

    async def command_name():
        if len(msg.attachments)!=0:
            async with msg.channel.typing():
                msg_to_send = await find_name(msg)
            if msg_to_send.find("TEMP_MESSAGE")!=-1:
                await msg.channel.send(content=msg_to_send.replace("TEMP_MESSAGE",""), delete_after=60)
            elif(msg_to_send != "❌"):
                await msg.channel.send(msg_to_send)
            else:
                delete_this = await msg.channel.send("Nope")
                await delete_this.delete()
                await msg.add_reaction("❌")

    async def command_boost_list():
        list_of_boost_users = msg.guild.premium_subscribers
        msg_to_send = ""
        if len(list_of_boost_users) == 0:
            msg_to_send = "No se encontraron usuarios boosteando este servidor"
        for user in list_of_boost_users:
            msg_to_send += "- " + str(user) + "\n"
        await msg.channel.send(msg_to_send)

    async def command_bot():
        msg_to_say = msg.content
        tmp_channel = msg.channel
        tmp_author = msg.author.display_name
        pfp_to_imitate = await msg.author.avatar_url.read()
        await msg.delete()

        msg_to_say = msg_to_say.replace("e!bot ","",1)
        msg_to_say = msg_to_say.replace("@everyone","")
        msg_to_say = msg_to_say.replace("@here","")
        webhook_discord = await tmp_channel.create_webhook(name=tmp_author, avatar=pfp_to_imitate, reason="EldoBOT: Temp-webhook")
        await webhook_discord.send(content = msg_to_say, username = tmp_author)#, allowed_mentions = allowed_mentions_NONE)
        # Delete webhook
        await webhook_discord.delete()

    async def command_anon_reset():
        tmp_user_id = msg.author.id
        if tmp_user_id in anon_list:
            del anon_list[tmp_user_id]
        await msg.channel.send(content="Tu perfil anónimo fué reseteado correctamente",delete_after=2.5)
        await msg.delete()

    async def command_anon_apodo():
        tmp_msg = msg.content
        tmp_channel = msg.channel
        tmp_user_id = msg.author.id
        tmp_guild_id = msg.guild.id
        await msg.delete()

        tmp_apodo = tmp_msg.replace("e!apodo ","",1)
        if tmp_apodo=="":
            await msg.channel.send(content="Tienes que escribit tu apodo después del comando **e!apodo **",delete_after=3)
        elif tmp_user_id in anon_list:
            anon_list[tmp_user_id]["apodo"] = tmp_apodo
            await msg.channel.send(content="Apodo cambiado correctamente",delete_after=2)
        else:
            anon_list[tmp_user_id] = {"apodo":tmp_apodo,"foto":"https://media.discordapp.net/attachments/647898356311654447/706938410098622555/unknown.png","guild":tmp_guild_id}
            await msg.channel.send(content="Apodo cambiado correctamente",delete_after=2)

        with open("anon_list.pkl", 'wb') as pickle_file:
            pickle.dump(anon_list,pickle_file)


    async def command_anon_photo():
        tmp_channel = msg.channel
        tmp_user_id = msg.author.id
        tmp_guild_id = msg.guild.id

        if len(msg.attachments)>0:
            attachment_file=await msg.attachments[0].to_file()
            tmp_msg = await channel_logs.send(content="Usuario: "+str(msg.author),file = attachment_file)
            tmp_msg_image_url = tmp_msg.attachments[0].url
            await msg.channel.send(content="Foto cambiada correctamente",delete_after=1.5)

        else:
            tmp_msg_image_url = "https://media.discordapp.net/attachments/647898356311654447/706938410098622555/unknown.png"
            await msg.channel.send(content="Tienes que adjuntar una foto junto al comando e!foto",delete_after=3)

        await msg.delete()

        if tmp_user_id in anon_list:
            anon_list[tmp_user_id]["foto"] = tmp_msg_image_url
        else:
            anon_list[tmp_user_id] = {"apodo":"Usuario Anónimo","foto":tmp_msg_image_url,"guild":tmp_guild_id}

        with open("anon_list.pkl", 'wb') as pickle_file:
            pickle.dump(anon_list,pickle_file)

    async def command_anon():
        msg_to_say = msg.content
        tmp_channel = msg.channel
        tmp_user_id = msg.author.id
        await msg.delete()

        if tmp_user_id in anon_list:
            tmp_avatar = anon_list[tmp_user_id]["foto"]
            tmp_author = anon_list[tmp_user_id]["apodo"]
        else:
            tmp_avatar = "https://media.discordapp.net/attachments/647898356311654447/706938410098622555/unknown.png"
            tmp_author = "Usuario Anónimo"

        msg_to_say = msg_to_say.replace("e!anon ","",1)
        msg_to_say = msg_to_say.replace("@everyone","")
        msg_to_say = msg_to_say.replace("@here","")
        webhook_discord = await tmp_channel.create_webhook(name=tmp_author, reason="EldoBOT: Temp-webhook Usuario-anónimo")
        await webhook_discord.send(content = msg_to_say, username = tmp_author, avatar_url = tmp_avatar)#, allowed_mentions = allowed_mentions_NONE)
        # Delete webhook
        await webhook_discord.delete()
        print("Confesión hecha!")

    async def command_say_like():
        msg_to_say = msg.content
        tmp_content = msg.content
        tmp_channel = msg.channel
        tmp_clean_msg = msg.clean_content
        tmp_author = msg.author.display_name
        tmp_raw_mentions = msg.raw_mentions[0]
        # Delete message
        await msg.delete()

        print(msg_to_say)
        if(tmp_content.lower().find("e!di como id:")==0):
            user_ID_to_imitate = re.findall('<(.*?)>', tmp_content)[0]
            msg_to_say = msg_to_say.replace("<"+user_ID_to_imitate+">","")
            msg_to_say = msg_to_say.replace("e!di como id:","")
            msg_to_say = tmp_clean_msg[tmp_clean_msg.find(msg_to_say[2:4]):] # Ohtia! Que es esto?? Pos... no hace falta entenderlo :P
        else:
            user_ID_to_imitate = str(tmp_raw_mentions)
            msg_to_say = msg_to_say.replace("e!di como","",1)
            msg_to_say = msg_to_say.replace("<@"+user_ID_to_imitate+">","")
            msg_to_say = msg_to_say.replace("<@!"+user_ID_to_imitate+">","")
            msg_to_say = tmp_clean_msg[tmp_clean_msg.find(msg_to_say[2:4]):] # WTF, porque?? Shhh

        # Solución temporal
        msg_to_say = msg_to_say.replace("@everyone","every**nyan**")
        msg_to_say = msg_to_say.replace("@here","nope")

        user_to_imitate = client.get_user(int(user_ID_to_imitate))
        if(user_to_imitate != None):
            pfp_to_imitate = await user_to_imitate.avatar_url.read()

            # Create Webhook
            webhook_discord = await tmp_channel.create_webhook(name=user_to_imitate.name, avatar=pfp_to_imitate, reason="EldoBOT: Temp-webhook")
            embed_to_send = discord.Embed(description=msg_to_say, colour=16761856).set_footer(text="Enviado por: " + tmp_author)
            # Send message
            await webhook_discord.send(embed = embed_to_send, username = user_to_imitate.display_name)#, allowed_mentions = allowed_mentions_NONE)
            print(msg_to_say," Printed!")
            # Delete webhook
            await webhook_discord.delete()
        else:
            print("User: "+user_ID_to_imitate+" not found")

    # This saves in a Databases what emojis where used by wich user and when, so we can do statistics later on
    async def save_emojis():
        if re.findall('<:(.*?)>', msg.content, re.DOTALL) or len("".join(c for c in msg.content if c in emoji.UNICODE_EMOJI))>0:
            raw_emojis_in_msg = re.findall('<:(.*?)>', msg.content, re.DOTALL)
            emojis_IDs = []
            emojis_call_names = []
            emojis_image_URL = []
            emojis_to_count = []
            mycursor.execute("SELECT emoji_id FROM emoji;")
            tmp_list_of_existing_IDs = mycursor.fetchall()
            list_of_existing_IDs=[]
            for element in tmp_list_of_existing_IDs:
                list_of_existing_IDs.append(element[0])

            # Creating a list of he emojis on the message, and saving information
            # about the ones that we are seeing for the first time
            for raw_emoji in raw_emojis_in_msg:
                temp_emojiID = raw_emoji[raw_emoji.find(":")+1:]
                emojis_to_count.append(str(temp_emojiID))
                if not (temp_emojiID in list_of_existing_IDs or temp_emojiID in emojis_IDs):
                    emojis_call_names.append(raw_emoji[:raw_emoji.find(":")])
                    emojis_IDs.append(temp_emojiID)
                    temp_emoji = client.get_emoji(int(emojis_IDs[-1]))
                    if(temp_emoji==None):
                        print(emojis_call_names[-1]+" emoji not found in the server. Adding it anyways")
                        emojis_image_URL.append("https://cdn.discordapp.com/emojis/"+str(emojis_IDs[-1])+".png")
                    else:
                        emojis_image_URL.append(str(temp_emoji.url))

            # Add the normie UNICODE emojis to the list
            normie_emoji_list= "".join(c for c in msg.content if c in emoji.UNICODE_EMOJI)
            for normie_emoji in normie_emoji_list:
                emojis_to_count.append(str(ord(normie_emoji)))
                if not (str(ord(normie_emoji)) in list_of_existing_IDs or str(ord(normie_emoji)) in emojis_IDs):
                    emojis_call_names.append(unicodedata.name(normie_emoji))
                    emojis_IDs.append(str(ord(normie_emoji)))
                    emojis_image_URL.append("https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/"+str(format(ord(normie_emoji),"x").upper())+".png")

            # Add new emojis to database
            mySQL_query = "INSERT INTO emoji (emoji_id, call_name, image_URL) VALUES (%s, %s, %s) "
            records_to_insert = tuple(zip(emojis_IDs, emojis_call_names, emojis_image_URL))
            mycursor.executemany(mySQL_query,records_to_insert)
            mydb.commit()
            if(len(records_to_insert)>0):
                print("We just added " + str(len(emojis_IDs))+" new emoji(s)! Here the list: "+str(emojis_call_names))

            # Checking if the writer of the message is already on our Database
            mycursor.execute("SELECT discordID FROM HelloWorld.user;")
            tmp_list_of_existing_IDs = mycursor.fetchall()
            list_of_existing_IDs=[]
            for element in tmp_list_of_existing_IDs:
                list_of_existing_IDs.append(element[0])
            if not str(msg.author.id) in list_of_existing_IDs:
                mySQL_query = "INSERT INTO user (discordID ,name, pictureURL) VALUES (%s, %s, %s) "
                mycursor.execute(mySQL_query,(str(msg.author.id), unidecode(msg.author.name).replace("DROP","DRO_P").replace("drop","dro_p").replace(";",",").replace("*","+"), str(msg.author.avatar_url)))
                mydb.commit()

            # Put the emoji + user in the database
            userID_list = [msg.author.id]*(len(emojis_to_count))
            guildID_list = [msg.guild.id]*(len(emojis_to_count))
            channelID_list = [msg.channel.id]*(len(emojis_to_count))
            records_to_insert = tuple(zip(emojis_to_count,userID_list,guildID_list,channelID_list))
            mySQL_query = "INSERT INTO emoji_log (emoji, user, guildID, channelID) VALUES (%s, %s, %s, %s) "
            mycursor.executemany(mySQL_query,records_to_insert)
            mydb.commit()

    msg_received = msg.content.lower()
    await save_emojis()

    if msg.content.find("spoiler") != -1:
        await command_spoiler()
    elif msg.content.lower().find("name") != -1 or msg.content.lower().find("nombre") != -1:
        await command_name()

    if msg_received[:2]==activator:
        msg_command = msg_received[2:]
        if  msg_command.find("emoji_stats")==0 and msg.author.display_name=="Eldoprano":
            await command_emoji_stats()
        elif msg_command == "help" or msg_command == "ayuda":
            await command_help()
        elif msg_command.find("conf") == 0 or msg_command.find("configurar") == 0:
            await command_config()
        elif msg_command.find("permitir name") == 0 or msg_command.find("permitir nombre") == 0:
            await command_config_permName()
        elif msg_command.find("bloquear name") == 0 or msg_command.find("bloquear nombre") == 0:
            await command_config_bloqName()
        elif msg_command.find("say") == 0 or msg_command.find("di") == 0:
            await command_say()
        elif msg_command.find("guilds") == 0 or msg_command.find("servidores") == 0:
            await command_guilds()
        elif msg_command == "ping" or msg_command == "test":
            await command_ping()
        elif msg_command == "boost list":
            await command_boost_list()
        elif msg_command.find("bot") == 0:
            await command_bot()
        elif msg_command =="reset" or msg_command == "resetear":
            await command_anon_reset()
        elif msg_command.find("apodo") == 0 or msg_command.find("nick") == 0:
            await command_anon_apodo()
        elif msg_command.find("foto") == 0 or msg_command.find("photo") == 0:
            await command_anon_photo()
        elif msg_command.find("e!anon ")==0 and (msg.channel.id==706925747792511056 or msg.guild.id==646799198167105539 or msg.author.permissions_in(msg.channel).manage_messages):
            await command_anon()
        elif msg_command.find("say") == 0 or msg_command.find("test") == 0:
            await command_ping()
        elif msg_command.find("di como")==0:
            await command_say_like()
        elif msg_command.find("qwertz")==0:
            await testTraceMoe()
        elif msg_command.find("qwerty")==0:
            print("Entering debug")
            await debugTraceMoe()


client.run(Discord_TOKEN)