from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from markdown import markdown
from telegraph import Telegraph
from telegraph.utils import html_to_nodes


def day_bounds_utc(target_date, target_tz):
    """Return the [start, end) UTC datetimes bounding ``target_date`` in ``target_tz``."""
    start_local = datetime.combine(target_date, time.min, tzinfo=target_tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


async def get_messages_for_date(
        client,
        channels,
        target_date,
        target_tz='Europe/Moscow'
    ):
    """Fetch all messages posted on ``target_date`` from each channel.

    Works for public channels even when the account is not a member: channels
    are resolved by their ``@username`` and history is read directly, without
    relying on dialog/read-state (which only exists for joined chats).
    """
    if isinstance(target_tz, str):
        target_tz = ZoneInfo(target_tz)
    day_start, day_end = day_bounds_utc(target_date, target_tz)
    messages = {}
    async with client:
        for channel_name in channels:
            messages[channel_name] = await get_channel_messages_for_date(
                client,
                channel_name,
                day_start,
                day_end,
                target_tz
            )
    return messages


async def get_channel_messages_for_date(client, channel_name, day_start, day_end, target_tz):
    channel = await client.get_entity(channel_name)

    day_messages = {}
    # iter_messages walks newest-to-oldest; offset_date excludes anything at or
    # after day_end, and we stop as soon as we cross below day_start.
    async for message in client.iter_messages(channel, offset_date=day_end):
        if message.date < day_start:
            break
        msg_dt_str = message.date.astimezone(target_tz).strftime(r'%Y-%m-%d %H:%M:%S')
        msg_body = message.message or '[Media]'
        day_messages[msg_dt_str] = msg_body

    day_messages = dict(reversed(day_messages.items()))

    return day_messages


def publish_summary(news_summary_content, access_token, author_name='News Summary Agent'):
    telegraph = Telegraph(access_token=access_token)
    title, _, content = news_summary_content.replace('## ', '### ').lstrip('\n').partition('\n')
    title = title.strip('# ')
    content = content.lstrip('\n')
    nodes = html_to_nodes(markdown(content))
    response = telegraph.create_page(
        title=title,
        content=nodes,
        author_name=author_name,
        return_content=False
    )
    return response


async def fast_forward(client, channels, ff_to_date):
    async with client:
        for channel_name in channels:
            channel = await client.get_entity(channel_name)
            message = await client.get_messages(
                channel,
                offset_date=ff_to_date,
                limit=1
            )
            await client.send_read_acknowledge(channel, max_id=message[0].id)
