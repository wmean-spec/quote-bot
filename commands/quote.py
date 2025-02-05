from vkbottle.bot import Blueprint, Message
from classes.abstract_command import AbstractCommand
from db.connect import db
from typing import Optional
from datetime import date, datetime
from iteration_utilities import deepflatten
import json
import aiohttp
from PIL import Image
from PIL import GifImagePlugin
import io
import os
from hashlib import blake2s
import logging

bp = Blueprint()

chats = 'chats.json'
config = 'config.json'

def config_load(config):
    with open(config, 'r') as f:
        return json.load(f)

config_content = config_load(config)

class Command(AbstractCommand):
    def __init__(self):
        super().__init__(handler=['/сьлржалсч', '/сьлржалсч —глубинность <deep>', '/сьлржалсч —d <deep>', '/СЬЛРЖАЛСЧ',
                                  '/СЬЛРЖАЛСЧ —глубинность <deep>', '/СЬЛРЖАЛСЧ —d <deep>'],
                         description='make quote from message; /сьлржалсч —d 0 to cut all reply and forward messages, 1 to cut all messages farther than 1 reply message')

Quote = Command()

async def get_pic_by_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            img_bytes = await resp.read()
    filename = f'{blake2s(img_bytes).hexdigest()}.webp'
    filepath = os.path.join(config_content['pics_dir'], filename)
    if not os.path.exists(filepath):
        with Image.open(io.BytesIO(img_bytes)) as img:
            img.save(filepath, 'WEBP', save_all=True)
    return f'/pics/{filename}'


async def get_photo(b):
    c = []
    for g in range(len(b)):
        c.append(b[g].height * b[g].width)
    url = b[c.index(max(c))].url
    return await get_pic_by_url(url)


def reverse_flat(a, deep, current_deep=0):
    if current_deep == deep:
        b = []
        for i in range(len(a)):
            if not isinstance(a[i], list):
                b.append(a[i])
        return b

    for i in range(len(a)):
        if isinstance(a[i], list):
            a.insert(i, reverse_flat(a[i], deep, current_deep + 1))
            a.pop(i + 1)

    return a


async def unpack(message, peer=None):
    mes = []
    if peer is not None:
        try:
            mess = await bp.api.messages.get_by_conversation_message_id(
                conversation_message_ids=message.conversation_message_id, peer_id=peer)
            if str(mess) != 'count=0 items=[]':
                message = mess.items[0]
        except Exception as e:
            logging.critical(e, exc_info=True)
    else:
        try:
            mess = await bp.api.messages.get_by_conversation_message_id(
                conversation_message_ids=message.conversation_message_id, peer_id=message.peer_id)
            if str(mess) != 'count=0 items=[]':
                message = mess.items[0]
        except Exception as e:
            logging.critical(e, exc_info=True)

    async def unpack_one(msg):
        images = []
        audio = ''
        if msg.attachments:
            for i in range(len(msg.attachments)):
                if msg.attachments[i].photo:
                    images.append(await get_photo(msg.attachments[i].photo.sizes))
                elif msg.attachments[i].doc:
                    images.append(await get_pic_by_url(msg.attachments[i].doc.url))
                elif msg.attachments[i].graffiti:
                    images.append(msg.attachments[i].graffiti.url)
                elif msg.attachments[i].sticker:
                    images.append(msg.attachments[i].sticker.images[-1].url)
                elif msg.attachments[i].audio_message:
                    audio = msg.attachments[i].audio_message.link_mp3
        if msg.from_id == abs(msg.from_id):
            user = await bp.api.users.get(msg.from_id)
            name = user[0].first_name + ' ' + user[0].last_name
            link = 'https://vk.com/id{}'.format(msg.from_id)
        else:
            user = await bp.api.groups.get_by_id(abs(msg.from_id))
            name = user[0].name
            link = 'https://vk.com/public{}'.format(abs(msg.from_id))
        if audio != '':
            return {"id": msg.from_id, "link": link, "name": name, "text": msg.text, "audio": audio, "images": []}
        else:
            return {"id": msg.from_id, "link": link, "name": name, "text": msg.text, "images": images}

    mes.append(await unpack_one(message))
    if message.reply_message:
        abc = message.reply_message
        if peer is not None:
            try:
                mess_reply = await bp.api.messages.get_by_conversation_message_id(
                    conversation_message_ids=message.reply_message.conversation_message_id, peer_id=peer)
                if str(mess_reply) != 'count=0 items=[]':
                    abc = mess_reply.items[0]
            except Exception as e:
                logging.critical(e, exc_info=True)
        else:
            try:
                mess_reply = await bp.api.messages.get_by_conversation_message_id(
                    conversation_message_ids=message.reply_message.conversation_message_id, peer_id=message.peer_id)
                if str(mess_reply) != 'count=0 items=[]':
                    abc = mess_reply.items[0]

            except Exception as e:
                logging.critical(e, exc_info=True)

        mes.append(await unpack(abc, peer))

    elif message.fwd_messages:
        for i in range(len(message.fwd_messages)):
            abc = message.fwd_messages[i]
            try:
                mess = await bp.api.messages.get_by_conversation_message_id(
                    conversation_message_ids=message.fwd_messages[i].conversation_message_id, peer_id=message.peer_id)
                if str(mess.items[0]) != 'count=0 items=[]':
                    abc = mess.items[0]
            except Exception as e:
                logging.critical(e, exc_info=True)

            mes.append(await unpack(abc))

    return mes


@bp.on.message(text=Quote.hdl())
async def quote(m: Message, deep: Optional[str] = None):
    id_chat = m.peer_id
    chat = config_load(chats)
    chat = chat["chats"]
    try:
        if m.reply_message:
            try:
                mes = await bp.api.messages.get_by_conversation_message_id(
                    conversation_message_ids=m.reply_message.conversation_message_id, peer_id=m.peer_id)
                if str(mes.items[0]) != 'count=0 items=[]':
                    mes = mes.items[0]
                else:
                    mes = m.reply_message
            except Exception as e:
                logging.critical(e, exc_info=True)
                
            unpacked_message = await unpack(mes, m.peer_id)
        elif m.fwd_messages:
            mes = await bp.api.messages.get_by_conversation_message_id(
                conversation_message_ids=m.conversation_message_id, peer_id=m.peer_id)
            if mes.items[0] != 'count=0 items=[]':
                mes = mes.items[0]
            else:
                mes = m.fwd_messages
            unpacked_message = await unpack(mes)
            unpacked_message.pop(0)
        if unpacked_message and isinstance(unpacked_message[0], list):
            unpacked_message = list(deepflatten(unpacked_message, ignore=dict, depth=1))
        if deep is not None:
            deep = int(deep)
            flat_unpack = list(deepflatten(unpacked_message, ignore=dict, depth=deep))

            unpacked_message = reverse_flat(unpacked_message, deep)

            b = []
            for i in range(len(flat_unpack)):
                if not isinstance(flat_unpack[i], list):
                    b.append(flat_unpack[i])
            flat_unpack = b

        flat_unpack = list(deepflatten(unpacked_message, ignore=dict))
        b = []
        for i in flat_unpack:
            b.append(i["name"])
        if unpacked_message and len(unpacked_message) == 1:

            qu = unpacked_message[0].get('text')
            au = unpacked_message[0].get('name')
            audio = None
            if "audio" in unpacked_message[0]:
                audio = unpacked_message[0].get('audio')

            images = unpacked_message[0].get('images')
            _id = unpacked_message[0].get('id')
            if audio or qu != '' or len(images) != 0:
                if _id == abs(_id):
                    link = 'https://vk.com/id{}'.format(_id)
                else:
                    link = 'https://vk.com/public{}'.format(abs(_id))

                today = date.today()
                d = today.strftime("%d.%m.%Y")
                t = str(datetime.now().time())[:5]
                time = d + ' в ' + t
                if audio:
                    quote_data = {"qu": qu, "au": au, "audio": audio, "images": images, "link": link, "da": time}
                else:
                    quote_data = {"qu": qu, "au": au, "images": images, "link": link, "da": time}
                if id_chat > 2000000000:
                    id_chat = id_chat - 2000000000
                    idss = []
                    for i in range(len(chat)):
                        idss.append(str(*chat[i]))
                    if str(id_chat) in idss:
                        cchat = chat[idss.index(str(id_chat))][str(id_chat)]
                        collection = db[cchat]
                        collection.insert_one(quote_data)
                    else:
                        cchat = chat[0]["0"]
                        collection = db[cchat]
                        collection.insert_one(quote_data)
                else:
                    cchat = chat[0]["0"]
                    collection = db[cchat]
                    collection.insert_one(quote_data)

                s = -1
                cursor = collection.find()
                for line in cursor:
                    s += 1

                await Quote.ans_up('https://quote.redmaun.site/' + cchat + '/' + str(s), m)
        else:
            qu = []

            if id_chat > 2000000000:
                id_chat = id_chat - 2000000000
                idss = []
                for i in range(len(chat)):
                    idss.append(str(*chat[i]))
                if str(id_chat) in idss:
                    cchat = chat[idss.index(str(id_chat))][str(id_chat)]
                    collection = db[cchat]
                
                else:
                    cchat = chat[0]["0"]
                    collection = db[cchat]
                    
            else:
                cchat = chat[0]["0"]
                collection = db[cchat]
                
            
            if b.count(b[0]) == len(b):
                for i in flat_unpack:
                    if "audio" in i:
                        y = str({'id': i["id"], 'audio': i["audio"], 'text': i["text"], 'images': i["images"]})
                    else:
                        y = str({'id': i["id"], 'text': i["text"], 'images': i["images"]})
                    a = str(i)
                    lcls = locals()
                    res = str(unpacked_message).replace(a, y)
                    exec('a = ' + res, globals(), lcls)
                    unpacked_message = lcls["a"]
                for i in range(len(unpacked_message)):
                    qu.append(unpacked_message[i])

                au = b[0]
                link = flat_unpack[0]["link"]
            else:
                for i in range(len(unpacked_message)):
                    qu.append(unpacked_message[i])
                try:
                    au = (await bp.api.messages.get_conversations_by_id(peer_ids=m.peer_id)).items[0].chat_settings.title
                except:
                    au = cchat

                link = ''

            today = date.today()
            d = today.strftime("%d.%m.%Y")
            t = str(datetime.now().time())[:5]
            time = d + ' в ' + t
            if link != '':
                quote_data = {"qu": qu, "au": au, "da": time, "link": link}
            else:
                quote_data = {"qu": qu, "au": au, "da": time}
            
            collection.insert_one(quote_data)

            s = -1
            cursor = collection.find()
            for line in cursor:
                s += 1

            await Quote.ans_up('https://quote.redmaun.site/' + cchat + '/' + str(s), m)

    except Exception as e:
        await Quote.ans_up(str(e), m)
