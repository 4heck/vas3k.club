import telegram
from django.conf import settings
from django.urls import reverse

from bot.common import Chat, ADMIN_CHAT, send_telegram_message, render_html_message


def notify_profile_needs_review(user, intro):
    user_profile_url = settings.APP_HOST + reverse("profile", kwargs={"user_slug": user.slug})
    send_telegram_message(
        chat=ADMIN_CHAT,
        text=render_html_message("moderator_need_review.html", user=user, intro=intro),
        reply_markup=telegram.InlineKeyboardMarkup([
            [
                telegram.InlineKeyboardButton("👍 Впустить", callback_data=f"approve_user:{user.id}"),
                telegram.InlineKeyboardButton("❌️ Отказать", callback_data=f"reject_user:{user.id}"),
            ],
            [
                telegram.InlineKeyboardButton("😏 Посмотреть", url=user_profile_url),
            ]
        ])
    )


def notify_user_profile_approved(user):
    user_profile_url = settings.APP_HOST + reverse("profile", kwargs={"user_slug": user.slug})

    if user.telegram_id:
        send_telegram_message(
            chat=Chat(id=user.telegram_id),
            text=f"🚀 Подравляем! Вы прошли модерацию. Добро пожаловать в Клуб!"
                 f"\n\nМожно пойти посмотреть свой профиль и заполнить там другие смешные поля:"
                 f"\n\n{user_profile_url}"
        )


def notify_user_profile_rejected(user):
    user_profile_url = settings.APP_HOST + reverse("profile", kwargs={"user_slug": user.slug})

    if user.telegram_id:
        send_telegram_message(
            chat=Chat(id=user.telegram_id),
            text=f"😐 К сожалению, ваш профиль не прошел модерацию. Но это не конец света и всё можно исправить."
                 f"Вот популярные причины почему так бывает:\n"
                 f"- Плохо написано #intro. Одного предложения обычно мало, нам же надо как-то познакомиться\n"
                 f"- Вымышленное имя или профессия\n"
                 f"- Много незаполненных полей\n"
                 f"\n\nВот ссылка чтобы податься на ревью еще раз: {user_profile_url}"
        )
