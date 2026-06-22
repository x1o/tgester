# from textwrap import dedent

import chatlas as ctl

from .tg import get_messages_for_date


def compile_prompt(
        scene=None,
        purpose=None,
        behaviour=None,
        examples=None,
        tools=None,
        follow_up=None
    ):
    prompt_list = [
        # Set the scene
        scene,
        # Define a purpose
        purpose,
        # Influence behavior
        behaviour,
        # Use specific examples
        examples,
        # Outline tasks: how exactly to use which tools
        tools,
        # Provide missing info
        # ...
        # Follow-up suggestions
        follow_up
    ]
    prompt = '\n\n'.join(p for p in prompt_list if p)
    return prompt


# summary_agent_prompt = compile_prompt(
#     scene = 'You are a news analyst.',
#     purpose = 'You will be asked to summarise news from several Telegram channels.',
#     behaviour = dedent('''
#     Your job is to provide an analytical news summary: group the news by major
#     topics (across the sources) and give a concise summary accurately describing
#     each topic based on corresponding news.  It's best to omit as few stories as
#     possible.  Aim at 15+ minute reading.

#     There will be some not-so-serious news pieces too - don't hesitate to summarise
#     them.

#     For Munich-related news, ignore weather & traffic reports completely.

#     Once again, consider all the topics. E.g. local Munich news are only slightly
#     less important than the global political / macroeconomic news.  Rather than
#     skipping "minor" news pieces, consider grouping them somehow, even if they
#     do not fit the standard news sections.  Listing many (10+) stories under one
#     section is perfectly fine.

#     At the very end, provide the summary statistics: which channels were sourced,
#     how many news stories processed, etc.

#     The source language is Russian. The summary must be in Russian as well.

#     Format the report as Markdown, suitable for rendering.
#     ''').strip(),
#     tools = dedent('''
#     To get the news stories you can use the `self.get_unread_messages()` tool.
#     ''').strip(),
#     follow_up = 'Do not suggest any further analysis.'
# )


summary_agent_prompt = """
## Role
You are a professional news analyst specialising in summarising news from various sources.

## Task
Analyze and summarize news from multiple Telegram channels, creating a
comprehensive analytical report using Markdown syntax. The request lists the
source channels, each with a short description of what it covers — use these
descriptions to group and attribute stories correctly.

## Output Requirements
1. Open with a short "Главное за день" lead (2-4 sentences) naming the day's
   principal threads, before the detailed sections.
2. Group news by major topics across all sources — organise by topic, not by channel.
3. When several channels report the same event, MERGE it into a single item and
   cite the sources in parentheses, e.g. "(@bbbreaking, @banksta)". Never repeat
   the same story under multiple bullets.
4. Be analytical, not a bare list of headlines: connect related stories and add
   context or implications where it is warranted.
5. Provide accurate summaries for each topic.
6. Include lighter/entertainment news as well.
7. For Munich news: skip weather and traffic.
8. Aim for 15+ minute reading time.
9. Include 10+ stories per section when appropriate - omit as few stories as possible.
10. Unrelated stories should go on their own lines, perhaps using markdown bullets.
    Do not mix them in the same paragraph.
11. Provide the Statistics section at the end, which includes the story count per
    channel and in total, date range, etc).
12. Do not echo your intentions, start with the analysis right away, i.e. do not
    add "I'll retrieve and analyze the news..." at the very beginning.
13. Use emojis if appropriate.
14. Consider all topics equally (local news are as important as global).

## Example (style of a merged, attributed item)
## 💸 Финансы
- **ЦБ снизил ключевую ставку до 16%** (@banksta, @russianmacro). Регулятор
  объяснил решение замедлением инфляции; @russianmacro добавляет, что рынок
  ожидал более осторожного шага, и связывает это с динамикой рубля.

## Language
- Input: Russian
- Output: Russian
""".strip()


class NewsSummaryAgent:
    def __init__(self, client, model_id='claude-sonnet-4-6', target_tz='Europe/Moscow',
                 max_tokens=32000, thinking=False):
        self.client = client
        self.target_tz = target_tz
        self.target_date = None
        self.thinking = thinking
        self.chat = ctl.ChatAnthropic(
            system_prompt=summary_agent_prompt,
            model=model_id,
            max_tokens=max_tokens,
            # A large max_tokens trips the SDK's non-streaming guard (it refuses
            # non-streaming requests estimated to exceed 10 min, i.e. above
            # ~21k tokens). An explicit client timeout suppresses that guard; the
            # digest itself finishes in a few minutes, well within this ceiling.
            kwargs={'timeout': 900}
        )
        self.chat.register_tool(self.get_channel_messages)

    async def get_channel_messages(
            self,
            channels: list[str]
        ) -> dict[str, list[dict[str, str]]]:
        '''
        Get all messages posted on the target date from the specified Telegram channels.

        Parameters
        ----------
        channels
            List of channel names to retrieve messages from

        Returns
        -------
            Mapping of channel names to a chronological list of messages,
            each {'time': timestamp, 'text': message content}

        Examples
        --------
        >>> news = await self.get_channel_messages(['@channel1', '@channel2'])
        >>> news['@channel1'][0]
        {'time': '2025-04-14 16:37:18', 'text': 'Lorem ipsum <...>'}
        '''
        return await get_messages_for_date(
            self.client,
            channels,
            self.target_date,
            self.target_tz
        )

    async def create_daily_summary(self, channels, target_date, descriptions=None, echo='none'):
        self.target_date = target_date
        descriptions = descriptions or {}
        source_lines = [
            f'- {ch} — {descriptions[ch]}' if descriptions.get(ch) else f'- {ch}'
            for ch in channels
        ]
        query = (
            f'Please summarise the news for {target_date:%Y-%m-%d} from the following '
            f'channels (the description after each handle indicates what the channel '
            f'covers):\n' + '\n'.join(source_lines)
        )
        extra = {'thinking': {'type': 'adaptive'}} if self.thinking else None
        response = self.chat.chat_async(
            query,
            stream=False,
            echo=echo,
            kwargs=extra
        )
        response = await response
        return response

    def __getattr__(self, name):
        return getattr(self.chat, name)

