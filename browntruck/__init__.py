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
import os

from aiohttp import web

from browntruck.news import news_hook


def create_app(*, github_token, github_payload_key, loop=None):
    app = web.Application(loop=loop)
    app["github_token"] = github_token
    app["github_payload_key"] = github_payload_key
    app.router.add_post("/hooks/news", news_hook)

    return app


def main(argv):
    loop = asyncio.get_event_loop()
    app = create_app(
        github_token=os.environ.get("GITHUB_TOKEN"),
        github_payload_key=os.environ.get("GITHUB_PAYLOAD_KEY"),
        loop=loop,
    )

    return app
