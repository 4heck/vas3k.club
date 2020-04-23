import logging
import re

from django.conf import settings
from django.urls import reverse
from telegram import Update

from bot.common import send_telegram_message, Chat
from comments.models import Comment
from users.models import User

COMMENT_URL_RE = re.compile(r"https?:[/|.|\w|\s|-]*/post/.+?/comment/([a-fA-F0-9\-]+)/")

log = logging.getLogger(__name__)


def process_comment_reply(update: Update):
    if not update.message.reply_to_message:
        return

    user = User.objects.filter(telegram_id=update.effective_user.id).first()
    if not user:
        send_telegram_message(
            chat=Chat(id=update.effective_user.id),
            text=f"😐 Извините, мы не знакомы. Привяжите свой аккаунт в профиле на https://vas3k.club"
        )
        return

    comment_url_entity = [
        entity["url"] for entity in update.message.reply_to_message.entities
        if entity["type"] == "text_link" and COMMENT_URL_RE.match(entity["url"])
    ]
    if not comment_url_entity:
        log.info(f"Comment url not found in: {update.message.reply_to_message.entities}")
        return

    reply_to_id = COMMENT_URL_RE.match(comment_url_entity[0]).group(1)
    reply = Comment.objects.filter(id=reply_to_id).first()
    if not reply:
        log.info(f"Reply not found: {reply_to_id}")
        return

    is_ok = Comment.check_rate_limits(user)
    if not is_ok:
        send_telegram_message(
            chat=Chat(id=update.effective_chat.id),
            text=f"🙅‍♂️ Извините, вы комментировали слишком часто и достигли дневного лимита"
        )
        return

    comment = Comment.objects.create(
        author=user,
        post=reply.post,
        reply_to=Comment.find_top_comment(reply),
        text=update.message.text,
        useragent="TelegramBot (like TwitterBot)",
        metadata={
            "telegram": update.to_dict()
        }
    )
    new_comment_url = settings.APP_HOST + reverse("show_comment", kwargs={
        "post_slug": comment.post.slug,
        "comment_id": comment.id
    })
    send_telegram_message(
        chat=Chat(id=update.effective_chat.id),
        text=f"➜ [Отвечено]({new_comment_url}) 👍"
    )
