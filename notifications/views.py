import random
from datetime import timedelta, datetime

from django.conf import settings
from django.db.models import Q, Count
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from comments.models import Comment, CommentVote
from common.flat_earth import parse_horoscope
from landing.models import GodSettings
from posts.models import Post, PostVote
from users.models import User


def email_confirm(request, user_id, secret):
    user = get_object_or_404(User, id=user_id, secret_hash=secret)

    user.is_email_verified = True
    user.save()

    return render(request, "message.html", {
        "title": "💌 Ваш адрес почты подтвержден",
        "message": "Теперь туда будет приходить еженедельный журнал Клуба и другие оповещалки."
    })


def email_unsubscribe(request, user_id, secret):
    user = get_object_or_404(User, id=user_id, secret_hash=secret)

    user.is_email_unsubscribed = True
    user.email_digest_type = User.EMAIL_DIGEST_TYPE_NOPE
    user.save()

    return render(request, "message.html", {
        "title": "🙅‍♀️ Вы отписались от всех писем Клуба",
        "message": "Мы ценим ваше время, потому отписали вас от всего и полностью. "
                   "Вы больше не получите от нас никаких писем. "
                   "Если захотите подписаться заново — напишите нам в поддержку."
    })


def email_digest_switch(request, digest_type, user_id, secret):
    user = get_object_or_404(User, id=user_id, secret_hash=secret)

    if not dict(User.EMAIL_DIGEST_TYPES).get(digest_type):
        return Http404()

    user.email_digest_type = digest_type
    user.is_email_unsubscribed = False
    user.save()

    if digest_type == User.EMAIL_DIGEST_TYPE_DAILY:
        return render(request, "message.html", {
            "title": "🔥 Теперь вы будете получать дейли-дайджест",
            "message": "Офигенно. "
                       "Теперь каждое утро вам будет приходить ваша персональная подборка всего нового в Клубе."
        })
    elif digest_type == User.EMAIL_DIGEST_TYPE_WEEKLY:
        return render(request, "message.html", {
            "title": "📅 Теперь вы получаете только еженедельный журнал",
            "message": "Раз в неделю вам будет приходить подбрка лучшего контента в Клубе за эту неделю. "
                       "Это удобно, качественно и не отнимает ваше время."
        })
    elif digest_type == User.EMAIL_DIGEST_TYPE_NOPE:
        return render(request, "message.html", {
            "title": "🙅‍♀️ Вы отписались от рассылок Клуба",
            "message": "Мы ценим ваше время, потому отписали вас от наших рассылок контента. "
                       "Можете следить за новыми постами в телеграме или через бота."
        })
    else:
        return render(request, "message.html", {
            "title": "👍 Данные подписки изменены",
            "message": ""
        })


def daily_digest(request, user_slug):
    user = get_object_or_404(User, slug=user_slug)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=1)
    if end_date.weekday() == 1:
        # we don't have daily on mondays and weekends, we need to include all these posts at tuesday
        start_date = end_date - timedelta(days=3)

    created_at_condition = dict(created_at__gte=start_date, created_at__lte=end_date)
    published_at_condition = dict(published_at__gte=start_date, published_at__lte=end_date)

    # Moon
    moon_phase = parse_horoscope()

    # New actions
    post_comment_actions = Comment.visible_objects()\
        .filter(
            post__author=user,
            **created_at_condition
        )\
        .values("post__type", "post__slug", "post__title")\
        .annotate(count=Count("id"))\
        .order_by()
    reply_actions = Comment.visible_objects()\
        .filter(
            reply_to__author=user,
            **created_at_condition
        )\
        .values("post__type", "post__slug", "post__title")\
        .annotate(count=Count("reply_to_id"))\
        .order_by()
    upvotes = PostVote.objects.filter(post__author=user, **created_at_condition).count() \
        + CommentVote.objects.filter(comment__author=user, **created_at_condition).count()

    new_events = [
        {
            "type": "post_comment",
            "post_url": reverse("show_post", kwargs={"post_type": e["post__type"], "post_slug": e["post__slug"]}),
            "post_title": e["post__title"],
            "count": e["count"],
        } for e in post_comment_actions
    ] + [
        {
            "type": "reply",
            "post_url": reverse("show_post", kwargs={"post_type": e["post__type"], "post_slug": e["post__slug"]}),
            "post_title": e["post__title"],
            "count": e["count"],
        } for e in reply_actions
    ] + [
        {
            "type": "upvotes",
            "count": upvotes,
        }
    ]

    # Best posts
    posts = Post.visible_objects()\
        .filter(is_approved_by_moderator=True, **published_at_condition)\
        .exclude(type__in=[Post.TYPE_INTRO, Post.TYPE_WEEKLY_DIGEST])\
        .order_by("-upvotes")[:100]

    # Best comments
    comments = Comment.visible_objects() \
        .filter(**created_at_condition) \
        .filter(is_deleted=False)\
        .order_by("-upvotes")[:1]

    # New joiners
    intros = Post.visible_objects()\
        .filter(type=Post.TYPE_INTRO, **published_at_condition)\
        .order_by("-upvotes")

    if not posts and not comments and not intros:
        raise Http404()

    return render(request, "emails/daily.html", {
        "user": user,
        "events": new_events,
        "intros": intros,
        "posts": posts,
        "comments": comments,
        "date": end_date,
        "moon_phase": moon_phase,
    })


def weekly_digest(request):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=8)  # make 8, not 7, to include marginal users

    created_at_condition = dict(created_at__gte=start_date, created_at__lte=end_date)
    published_at_condition = dict(published_at__gte=start_date, published_at__lte=end_date)

    # New users
    intros = Post.visible_objects()\
        .filter(type=Post.TYPE_INTRO, **published_at_condition)\
        .order_by("-upvotes")
    newbie_count = User.objects\
        .filter(is_profile_reviewed=True, **created_at_condition)\
        .count()

    # Best posts
    featured_post = Post.visible_objects()\
        .exclude(type=Post.TYPE_INTRO)\
        .filter(
            label__isnull=False,
            label__code="top_week",
            **published_at_condition
         )\
        .order_by("-upvotes")\
        .first()

    posts = Post.visible_objects()\
        .filter(is_approved_by_moderator=True, **published_at_condition)\
        .exclude(type__in=[Post.TYPE_INTRO, Post.TYPE_WEEKLY_DIGEST])\
        .exclude(id=featured_post.id if featured_post else None)\
        .order_by("-upvotes")[:12]

    # Video of the week
    top_video_comment = Comment.visible_objects() \
        .filter(**created_at_condition) \
        .filter(is_deleted=False)\
        .filter(upvotes__gte=3)\
        .filter(Q(text__contains="https://youtu.be/") | Q(text__contains="youtube.com/watch"))\
        .order_by("-upvotes")\
        .first()

    top_video_post = None
    if not top_video_comment:
        top_video_post = Post.visible_objects() \
            .filter(type=Post.TYPE_LINK, upvotes__gte=3) \
            .filter(**published_at_condition) \
            .filter(Q(url__contains="https://youtu.be/") | Q(url__contains="youtube.com/watch")) \
            .order_by("-upvotes") \
            .first()

    # Best comments
    comments = Comment.visible_objects() \
        .filter(**created_at_condition) \
        .filter(is_deleted=False)\
        .exclude(id=top_video_comment.id if top_video_comment else None)\
        .order_by("-upvotes")[:3]

    # Intro from author
    author_intro = GodSettings.objects.first().digest_intro

    if not author_intro and not posts and not comments:
        raise Http404()

    return render(request, "emails/weekly_digest.html", {
        "posts": posts,
        "comments": comments,
        "intros": intros,
        "newbie_count": newbie_count,
        "top_video_comment": top_video_comment,
        "top_video_post": top_video_post,
        "featured_post": featured_post,
        "author_intro": author_intro,
        "issue_number": (end_date - settings.LAUNCH_DATE).days // 7
    })
