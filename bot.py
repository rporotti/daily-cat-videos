#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0613, C0116
# type: ignore[union-attr]

import logging
import numpy as np
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import boto3
import botocore
import datetime
import time
import pytz

if os.environ.get("WITH_AWS", None):
    session = boto3.Session(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", None),
    )
    s3 = session.resource('s3')


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
token = os.environ.get("TOKEN", None)


def send_to_S3():
    # Filename - File to upload
    # Bucket - Bucket to upload to (the top level directory under AWS S3)
    # Key - S3 object name (can contain subdirectories). If not specified then file_name is used
    s3.meta.client.upload_file(Filename="subscribed_users.txt", Bucket=os.environ.get("S3_BUCKET_NAME", None), Key="subscribed_users.txt")

def get_from_S3():
    try:
        s3.Bucket(os.environ.get("S3_BUCKET_NAME", None)).download_file("subscribed_users.txt", "subscribed_users.txt")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist.")
        else:
            raise


        
logger = logging.getLogger(__name__)
PORT = int(os.environ.get('PORT', '8443'))

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi!')


def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def random(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""
    with open("videos.txt", "r") as f:
        videos = [line.strip("\n") for line in f if line != "\n"]
    
    update.message.reply_text(videos[np.random.randint(len(videos))])

def latest(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""
    with open("videos.txt", "r") as f:
        videos = [line.strip("\n") for line in f if line != "\n"]
    
    update.message.reply_text(videos[-1])
    
def restart(updater):
    if os.path.isfile("subscribed_users.txt"):
        with open("subscribed_users.txt", "r") as su:
            lines = [s.split(" ") for s in su.readlines()]
            subscribed_users = [s[0] for s in lines]
            times = [s[1] for s in lines]
    else:
        subscribed_users = []
        times = []


    for (user, time_str) in zip(subscribed_users, times):
        hour=time_str.split(":")[0]
        minutes=time_str.split(":")[1]
        updater.job_queue.run_daily(
            latest_job,
            datetime.time(hour=int(hour), minute=int(minutes), tzinfo=pytz.timezone("Europe/Rome")),
            days=(0, 1, 2, 3, 4, 5, 6),
            context=user,
            name=user,
        )

def latest_job(context):
    with open("videos.txt", "r") as f:
        videos = [line.strip("\n") for line in f if line != "\n"]
    
    job = context.job
    
    context.bot.send_message(
        job.context, text=videos[-1]
    )
    context.bot.send_message(
        job.context, text="See you tomorrow for another daily cat video!"
    )


def subscribe(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    
    
    if is_subscribed(str(chat_id), context):
        text = "You are already subscribed."
    else:
        if len(update.message.text.split(" "))==1:
            text="Please choose a time in the following format: {hour}:{minutes}"
        else:
            try:
                time_str=update.message.text.split(" ")[1]
                time.strptime(time_str, '%H:%M')
                flag=True
            except ValueError:
                text="Wrong format for time! Please use {hour}:{minutes}"
                flag=False
            if flag==True:
                hour=time_str.split(":")[0]
                minutes=time_str.split(":")[1]
                context.job_queue.run_daily(
                    latest_job,
                    datetime.time(hour=int(hour), minute=int(minutes), tzinfo=pytz.timezone("Europe/Rome")),
                    days=(0, 1, 2, 3, 4, 5, 6),
                    context=chat_id,
                    name=str(chat_id),
                )
                with open("subscribed_users.txt", "a") as su:
                    su.write(str(chat_id) + " ")
                    su.write("{0}:{1}".format(hour, minutes) + "\n")
                if os.environ.get("WITH_AWS", None):
                    send_to_S3()
                text = "You will receive a daily cat video at {0}:{1}!".format(hour, minutes)

    update.message.reply_text(text)

def is_subscribed(name, context):
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    return True


def remove_subscription(name, context):
    for job in context.job_queue.get_jobs_by_name(name):
        job.schedule_removal()

    with open("subscribed_users.txt", "r") as su:
        users = su.readlines()

    with open("subscribed_users.txt", "w") as su:
        for user in users:
            if user.split(" ")[0] != name:
                su.write(user)
    if os.environ.get("WITH_AWS", None):
        send_to_S3()
        

    
    
    
def unsubscribe(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id

    if is_subscribed(str(chat_id), context):
        remove_subscription(str(chat_id), context)
        text = "You will no longer receive the latest updates. \U0001f62d"
    else:
        text = (
            "You are not currently subscribed. Use /subscribe to receive daily updates."
        )
    update.message.reply_text(text)


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(token, use_context=True)
    
    if os.environ.get("WITH_AWS", None):
        get_from_S3()
    restart(updater)
    


    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("random", random))
    dispatcher.add_handler(CommandHandler("latest", latest))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Start the Bot
    #updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    
    if os.environ.get("IS_HEROKU", None):
        updater.start_webhook(listen="0.0.0.0",
                              port=PORT,
                              url_path=token)
        # updater.bot.set_webhook(url=settings.WEBHOOK_URL)
        updater.bot.set_webhook(
                "https://{}.herokuapp.com/".format(os.environ.get(
                "APP_NAME", None)) + token)
    else:
        updater.start_polling()
    
    updater.idle()


if __name__ == '__main__':
    main()
