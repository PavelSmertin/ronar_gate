import time
import pika
import redis

from flask import Flask
from flask import render_template
from flask import request
from flask_socketio import SocketIO
from flask_socketio import send, emit

import telebot

from threading import Thread



API_TOKEN = '839592315:AAH8wX2K6ojVExaYPB7F8fuE6rXO52rk11k'

bot = telebot.TeleBot(API_TOKEN)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
cache = redis.Redis(host='redis', port=6379)

def get_hit_count():
    retries = 5
    while True:
        try:
            return cache.incr('hits')
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)

def __logHex(msg):
    if not msg:
        return
    return " ".join(["{:02x}".format(x).upper() for x in msg])
def __keyConcat(msg):
        return "".join(["{:02x}".format(x).upper() for x in msg])

@app.route('/')
def hello():
    count = get_hit_count()


    # Process(target=sub_response).start()
    # Process(target=sub_request).start()

    # messages_in = [(k, __logHex(v)) for k, v in cache.hgetall("in").items()]
    # messages_out = [(k, __logHex(v)) for k, v in cache.hgetall("out").items()]

    messages_in = []
    for k,v in cache.hgetall("in").items():
        if(k[0:1] == b'\x00'):
            request = cache.hget("in", k)
            response = cache.hget("in", b'\xFF'+k[1:3])
            messages_in.append((__keyConcat(k[1:3]), [__logHex(request), __logHex(response)]))

    messages_out = []
    for k,v in cache.hgetall("out").items():
        if(k[0:1] == b'\x00'):
            request = cache.hget("out", k)
            response = cache.hget("out", b'\xFF'+k[1:3])
            messages_out.append((__keyConcat(k[1:3]), [__logHex(request), __logHex(response)]))

    return render_template("index.html",
        title = 'Home',
        messages_in = messages_in,
        messages_out = messages_out
        )

    # return 'this is a commands gate. it have been seen {} times.\n'.format(count)

@app.route('/send_command', methods=['POST'])
def command():

    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='text')

    message = request.form['command']
    try:
        message = bytes.fromhex(message)
    except:
        return "ты ебнутый?", 422

    channel.basic_publish(
        exchange='', 
        routing_key='text', 
        body=message
    )
    response = __logHex(message)
    connection.close()
    return 'Command sent: {} \n'.format(response)

def sub_stream():
    pubsub = cache.pubsub()
    pubsub.subscribe(['stream'])
    for item in pubsub.listen():
        if isinstance(item['data'], bytes):
            socketio.emit('transaction', get_emit(item['data']))

def sub_events():
    pubsub = cache.pubsub()
    pubsub.subscribe(['events'])
    for item in pubsub.listen():
        if item['data'] == 1:
            continue

        # bot.send_message('-344086809', tele_msg)
        bot.send_message('-1001485120003', item['data'])

def get_emit(msg):
    return { 
        'type': "{:02x}".format(msg[2]).upper(), 
        'id': "".join(["{:02x}".format(x).upper() for x in msg[0:2]]), 
        'data': " ".join(["{:02x}".format(x).upper() for x in msg[2:]])
    }

def get_command(msg):
    return False #" ".join(["{:02x}".format(x).upper() for x in msg[2:]])


# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message, message.chat.id)


# Handle all other messages with content_type 'text' (content_types defaults to ['text'])
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    bot.reply_to(message, message.chat.id)


def start_bot():
    bot.polling()

if __name__ == '__main__':
    Thread(target=sub_stream).start()
    Thread(target=sub_events).start()
    Thread(target=start_bot).start()
    socketio.run(app, host='0.0.0.0', port=5000)


