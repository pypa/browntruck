# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import functools
import os
import urllib.parse

import aioredis

from aiocron import crontab
from aiohttp import web

from browntruck.news import news_hook
from browntruck.rebase import check_prs, needs_rebase_hook


async def _create_redis_pool(app):
    p = urllib.parse.urlparse(app["redis.url"])
    app["redis.pool"] = await aioredis.create_pool(
        (p.hostname, p.port),
        password=p.password,
    )


async def _shutdown_redis_pool(app):
    app["redis.pool"].close()
    await app["redis.pool"].wait_closed()


def create_app(*, github_token, github_payload_key,
               github_app_id,
               github_app_private_key,
               # github_app_webhook_secret,  # seems == github_payload_key
               repo, redis_url,
               loop=None):
    app = web.Application(loop=loop)
    app["repo"] = repo
    app["github_token"] = github_token
    app["github_payload_key"] = github_payload_key
    app["github_app_id"] = github_app_id
    app["github_app_private_key"] = github_app_private_key
    # app["github_app_webhook_secret"] = github_app_webhook_secret
    app["redis.url"] = redis_url

    app.on_startup.append(_create_redis_pool)

    app.on_cleanup.append(_shutdown_redis_pool)

    app.router.add_post("/hooks/news", news_hook)
    app.router.add_post("/hooks/rebase", needs_rebase_hook)

    app["cron.rebase.check_prs"] = crontab("*/15 * * * *",
                                           functools.partial(check_prs, app),
                                           loop=loop)

    return app


def main(argv):
    loop = asyncio.get_event_loop()
    app = create_app(
        github_token=os.environ.get("GITHUB_TOKEN"),
        github_payload_key=os.environ.get("GITHUB_PAYLOAD_KEY"),
        # GitHub App integration credentials:
        github_app_id=os.environ.get("GITHUB_APP_IDENTIFIER"),
        github_app_private_key=os.environ.get("GITHUB_PRIVATE_KEY"),
        # github_app_webhook_secret=os.environ.get("GITHUB_WEBHOOK_SECRET"),  # seems to be the same as github_payload_key
        # GitHub App integration credentials end
        repo=os.environ.get("REPO"),
        redis_url=os.environ.get("REDIS_URL"),
        loop=loop,
    )

    return app
